import { useEffect, useRef, useState, type FormEvent } from 'react';
import { api, type Incident, type System } from '../api/client';
import { Badge, Empty, ErrorNotice, Icon } from '../components';
import { Markdown } from '../markdown';

type Cited = { event_id: string; label: string; clip_url: string | null; start_ms: number; poster_url: string | null };

interface RetrievalPlanOut {
  intent: string;
  sources: string[];
  rewritten_query: string;
}

interface EvidenceItem {
  id: string;
  kind: string;
  title: string;
  subtitle?: string | null;
  snippet: string;
  media_url?: string | null;
  timestamp?: string | null;
}

interface ConversationSummary {
  id: string;
  title: string;
  message_count: number;
  last_message_preview?: string | null;
}

type DigestFrame = { url: string; t_ms: number; alert: boolean };
type DigestItem = {
  source_id: string;
  filename: string;
  uploaded_label: string;
  status: string | null;
  duration_s: number | null;
  objects: Record<string, number>;
  alerts: { label: string; t_ms: number; confidence: number; status: string | null }[];
  frames: DigestFrame[];
  video_url: string | null;
  summary: string | null;
  summary_kind: 'pending' | 'ai' | 'facts' | 'unavailable';
};
type Digest = { window: string; total: number; hidden: number; items: DigestItem[] };

type Message = {
  role: 'user' | 'assistant';
  text: string;
  eventIds: string[];
  cited: Cited[];
  plan?: RetrievalPlanOut;
  evidence?: EvidenceItem[];
  digest?: Digest;
  status?: string;
  model?: string;
};

const PROMPTS = [
  'Summarize all the videos uploaded in the past hour.',
  'Which videos were uploaded today, and what happens in them?',
  'Summarize the most recent incident and what the footage shows.',
  'Which rulesets and camera rules are currently active?',
  'What is happening right now on the live cameras?',
  'Which incidents still need human review?',
];

function clock(ms: number) {
  if (ms < 60000) return `${(ms / 1000).toFixed(1)} s`;
  const seconds = Math.round(ms / 1000);
  return `${Math.floor(seconds / 60)}:${String(seconds % 60).padStart(2, '0')}`;
}

function DigestCard({ item }: { item: DigestItem }) {
  const [playAt, setPlayAt] = useState<number | null>(null);
  const waiting = item.summary_kind === 'pending';
  const length = item.duration_s ? (item.duration_s < 90 ? `${Math.round(item.duration_s)} s` : `${Math.floor(item.duration_s / 60)} min ${String(Math.round(item.duration_s % 60)).padStart(2, '0')} s`) : null;
  return (
    <article className="digest-card">
      <header>
        <strong>{item.filename}</strong>
        <small>Uploaded {item.uploaded_label}{length ? ` · ${length}` : ''}</small>
        {item.status && item.status !== 'DONE' && <Badge>{item.status.toLowerCase()}</Badge>}
      </header>
      {playAt !== null && item.video_url && (
        <video
          controls
          autoPlay
          preload="metadata"
          src={item.video_url}
          onLoadedMetadata={(e) => {
            e.currentTarget.currentTime = playAt / 1000;
          }}
        />
      )}
      <div className="digest-frames" aria-label={`Key frames of ${item.filename}`}>
        {item.frames.map((frame) => (
          <button type="button" key={frame.url} className="digest-frame" disabled={!item.video_url} onClick={() => setPlayAt(frame.t_ms)} aria-label={`Play ${item.filename} from ${clock(frame.t_ms)}`}>
            <img src={frame.url} alt={`Key frame at ${clock(frame.t_ms)}`} loading="lazy" />
            <span>{clock(frame.t_ms)}</span>
            {frame.alert && <em>alert</em>}
          </button>
        ))}
        {!item.frames.length && waiting && <div className="digest-frame skeleton-frame" aria-hidden="true" />}
      </div>
      <p className={`digest-summary ${item.summary_kind}`}>{item.summary || 'Looking at this video…'}</p>
      {(Object.keys(item.objects).length > 0 || item.alerts.length > 0) && (
        <div className="digest-chips">
          {Object.entries(item.objects).map(([name, count]) => <Badge key={name}>{name} × {count}</Badge>)}
          {item.alerts.slice(0, 3).map((alert, i) => <Badge key={i}>⚠ {alert.label} at {clock(alert.t_ms)} · {Math.round(alert.confidence * 100)}%</Badge>)}
        </div>
      )}
    </article>
  );
}

function DigestView({ digest }: { digest: Digest }) {
  const many = digest.total === 1 ? '' : 's';
  return (
    <div className="digest">
      <p className="digest-head"><strong>{digest.total} video{many}</strong> · {digest.window} · newest first</p>
      {digest.items.map((item) => <DigestCard key={item.source_id} item={item} />)}
      {digest.hidden > 0 && <p className="caption">{digest.hidden} older video{digest.hidden === 1 ? '' : 's'} in this window are not shown. Ask for a shorter time span to see them.</p>}
      <p className="caption">Descriptions are written by the local model from a few key frames per video, so they can miss or misread details. Click a frame to play the video from there.</p>
    </div>
  );
}

function Footage({ item }: { item: Cited & { clip_url: string } }) {
  return (
    <figure className="footage">
      <div className="media-stage" style={{ width: '100%', aspectRatio: '16 / 9' }}>
        <video
          controls
          preload="metadata"
          poster={item.poster_url || undefined}
          src={item.clip_url}
          style={{ width: '100%', height: '100%', aspectRatio: '16 / 9', objectFit: 'cover', display: 'block' }}
          onLoadedMetadata={(e) => {
            e.currentTarget.currentTime = item.start_ms / 1000;
          }}
        />
      </div>
      <figcaption>{item.label} · playback starts just before the detection</figcaption>
    </figure>
  );
}

export function Investigation({
  events,
  scope,
  setScope,
  onOpen,
  system,
}: {
  events: Incident[];
  scope: string | null;
  setScope: (id: string | null) => void;
  onOpen: (e: Incident) => void;
  system: System | null;
}) {
  const [messages, setMessages] = useState<Message[]>([]);
  const [input, setInput] = useState('');
  const [provider, setProvider] = useState<'ollama' | 'groq'>('ollama');
  const [images, setImages] = useState(true);
  const [conversation, setConversation] = useState<string | null>(null);
  const [conversations, setConversations] = useState<ConversationSummary[]>([]);
  const [historyOpen, setHistoryOpen] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const abort = useRef<AbortController>();
  const messagesPane = useRef<HTMLDivElement>(null);
  const historyDialog = useRef<HTMLDialogElement>(null);
  const groq = Boolean(system?.chat.groq_configured);
  const latestAnswer = [...messages].reverse().find((message) => message.role === 'assistant');
  const relatedFootage = (latestAnswer?.digest ? [] : latestAnswer?.cited || []).map((citation) => {
    if (citation.clip_url) return citation as Cited & { clip_url: string };
    const event = events.find((item) => item.id === citation.event_id);
    const clip = event?.media?.find((item) => item.kind === 'CLIP');
    const frame = event?.media?.find((item) => item.kind === 'KEYFRAME');
    return clip ? { ...citation, clip_url: clip.url, poster_url: citation.poster_url || frame?.url || null, start_ms: citation.start_ms || clip.offset_ms || 0 } : null;
  }).filter((item): item is Cited & { clip_url: string } => item !== null);

  useEffect(() => {
    if (groq) setProvider(String(system?.chat.chat_provider) === 'groq' ? 'groq' : 'ollama');
  }, [groq, system?.chat.chat_provider]);

  useEffect(() => {
    if (messages.length && messagesPane.current) {
      messagesPane.current.scrollTo({ top: messagesPane.current.scrollHeight, behavior: 'smooth' });
    }
  }, [messages]);

  useEffect(() => {
    if (historyOpen) historyDialog.current?.showModal();
  }, [historyOpen]);

  const loadConversations = async () => {
    try {
      const list = await api<{ items: ConversationSummary[] }>('/chat/conversations');
      setConversations(list.items);
    } catch {
      // ignore if empty
    }
  };

  useEffect(() => {
    void loadConversations();
  }, []);

  async function openConversation(id: string) {
    try {
      const saved = await api<{ id: string; messages: { role: 'user' | 'assistant'; content: string; digest?: Digest }[] }>(`/chat/conversations/${id}`);
      setConversation(saved.id);
      setMessages(saved.messages.map((message) => ({ role: message.role, text: message.content, eventIds: [], cited: [], digest: message.digest })));
      setError(null);
    } catch (cause) {
      setError((cause as Error).message);
    }
  }

  const patch = (change: (m: Message) => Message) =>
    setMessages((old) => old.map((m, i) => (i === old.length - 1 ? change(m) : m)));
  const openEvent = (id: string) => {
    const found = events.find((e) => e.id === id);
    if (found) onOpen(found);
  };

  async function ask(question: string) {
    if (!question.trim() || busy) return;
    setInput('');
    setBusy(true);
    setError(null);
    setMessages((old) => [
      ...old,
      { role: 'user', text: question, eventIds: [], cited: [] },
      { role: 'assistant', text: '', eventIds: [], cited: [], status: 'Planning evidence retrieval…' },
    ]);
    abort.current = new AbortController();
    try {
      const response = await fetch('/api/v1/chat/stream', {
        method: 'POST',
        credentials: 'include',
        signal: abort.current.signal,
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          message: question,
          conversation_id: conversation,
          provider,
          event_ids: scope ? [scope] : [],
          include_images: images,
        }),
      });
      if (!response.ok) throw new Error(`Chat request failed (${response.status})`);
      const reader = response.body!.getReader();
      const decoder = new TextDecoder();
      let buffer = '';
      for (;;) {
        const { value, done } = await reader.read();
        if (done) break;
        buffer += decoder.decode(value, { stream: true });
        const lines = buffer.split('\n');
        buffer = lines.pop() || '';
        for (const line of lines) {
          if (!line) continue;
          const item = JSON.parse(line);
          if (item.type === 'error') throw new Error(item.message);
          if (item.type === 'plan') {
            patch((m) => ({ ...m, plan: item.plan as RetrievalPlanOut, status: 'Retrieving grounded evidence…' }));
          }
          if (item.type === 'evidence') {
            const items = (item.items || []) as EvidenceItem[];
            patch((m) => ({ ...m, evidence: items }));
          }
          if (item.type === 'context') {
            setConversation(item.conversation_id);
            patch((m) => ({ ...m, eventIds: item.event_ids || [], model: item.model, status: 'Synthesizing grounded answer…' }));
          }
          if (item.type === 'status') patch((m) => ({ ...m, status: item.message }));
          if (item.type === 'digest') {
            patch((m) => ({ ...m, digest: { window: item.window?.label || '', total: item.total, hidden: item.hidden, items: item.items as DigestItem[] } }));
          }
          if (item.type === 'digest_item') {
            const updated = item.item as DigestItem;
            patch((m) => (m.digest ? { ...m, digest: { ...m.digest, items: m.digest.items.map((card) => (card.source_id === updated.source_id ? updated : card)) } } : m));
          }
          if (item.type === 'delta') patch((m) => ({ ...m, text: m.text + item.text, status: m.digest ? m.status : undefined }));
          if (item.type === 'done') {
            patch((m) => ({ ...m, text: item.answer || m.text, model: item.model, cited: item.cited || [], digest: item.digest || m.digest, status: undefined }));
            void loadConversations();
          }
        }
      }
    } catch (e) {
      if ((e as Error).name !== 'AbortError') setError((e as Error).message);
    } finally {
      setBusy(false);
      abort.current = undefined;
      patch((m) => ({ ...m, status: undefined }));
    }
  }

  const submit = (e: FormEvent) => {
    e.preventDefault();
    void ask(input.trim());
  };

  return (
    <>
    <div className={`chat-layout ${relatedFootage.length ? 'has-evidence' : 'no-evidence'} ${messages.length ? 'has-messages' : 'is-empty'}`}>
      <section className="panel chat-panel">
        <div className="chat-topline"><h2>Conversation</h2><div className="chat-top-actions"><button type="button" onClick={() => setHistoryOpen(true)}>Past chats{conversations.length > 0 && <span className="chat-history-count">{conversations.length}</span>}</button><button type="button" onClick={() => { setConversation(null); setMessages([]); setInput(''); }}>New chat</button></div></div>
        <details className="chat-options"><summary><span>Search options</span><small>{scope ? 'One incident' : 'All recent incidents'} · {provider === 'ollama' ? 'Local AI' : 'Groq'}</small><Icon name="chevron-down" size={18}/></summary><div className="chat-toolbar">
          <select aria-label="Chat provider" value={provider} onChange={(e) => setProvider(e.target.value as 'ollama' | 'groq')}>
            <option value="ollama">Local · {String(system?.chat.ollama_model || 'Gemma')}</option>
            <option value="groq" disabled={!groq}>
              Groq · {String(system?.chat.groq_model || 'Qwen')}
            </option>
          </select>
          <select
            aria-label="Incident scope"
            value={scope || ''}
            onChange={(e) => {
              setScope(e.target.value || null);
              setConversation(null);
              setMessages([]);
            }}
          >
            <option value="">All recent incidents & cameras</option>
            {events.map((e) => (
              <option key={e.id} value={e.id}>
                {e.category.label} · {e.camera.name}
              </option>
            ))}
          </select>
        </div>
        <p className="caption">
          {provider === 'groq'
            ? 'Your question, incident metadata and the selected evidence frames are sent to Groq. Full recordings stay on your PC.'
            : 'This chat runs on your local server. Full recordings stay on your PC.'}
        </p>
        <label className="checkbox">
          <input type="checkbox" checked={images} onChange={(e) => setImages(e.target.checked)} />
          Let the assistant inspect live camera keyframes & incident evidence frames
        </label></details>
        <div className="messages" ref={messagesPane} aria-live="polite">
          {messages.length ? (
            messages.map((m, i) => (
              <div className={`message ${m.role}`} key={i}>
                <span className="eyebrow">{m.role === 'user' ? 'YOU' : `SAFESPACE${m.model ? ' · ' + m.model : ''}`}</span>
                {m.role === 'user' ? (
                  <p>{m.text}</p>
                ) : (
                  <>
                    {m.digest ? (
                      <DigestView digest={m.digest} />
                    ) : m.text ? (
                      <Markdown text={m.text} onEvent={openEvent} />
                    ) : (
                      <p className="status-line">{m.status || (busy ? 'Connecting to the model…' : 'No response received.')}</p>
                    )}
                    {m.status && m.text && <p className="status-line">{m.status}</p>}
                    {m.cited.length > 0 && !m.digest && <div className="citation-links">{m.cited.map((citation) => <button type="button" key={`${citation.event_id}-${citation.label}`} onClick={() => document.getElementById('chat-evidence')?.scrollIntoView({ behavior: 'smooth', block: 'start' })}><Icon name="play-01" size={14}/> {citation.label}</button>)}</div>}
                  </>
                )}
              </div>
            ))
          ) : (
            <Empty title="What would you like to know?" icon="search-01">
              Ask about an incident, a rule, or what your cameras can see.
              <span className="prompt-chips">
                {PROMPTS.map((p) => (
                  <button key={p} type="button" onClick={() => void ask(p)}>
                    {p}
                  </button>
                ))}
              </span>
            </Empty>
          )}
        </div>
        <ErrorNotice message={error} />
        <form className="chat-composer" onSubmit={submit}>
          <textarea
            aria-label="Ask about incidents"
            rows={2}
            placeholder="What happened in the most recent incident, or what is visible on the live camera?"
            value={input}
            maxLength={4000}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === 'Enter' && !e.shiftKey) {
                e.preventDefault();
                e.currentTarget.form?.requestSubmit();
              }
            }}
          />
          {busy ? (
            <button type="button" onClick={() => abort.current?.abort()}>
              <Icon name="pause-01" />
              Stop
            </button>
          ) : (
            <button className="primary" disabled={!input.trim()} aria-label="Send question">
              <Icon name="search-01" />
              Ask
            </button>
          )}
        </form>
      </section>

      {relatedFootage.length > 0 && <aside className="panel chat-evidence" id="chat-evidence">
        <div className="section-head">
          <div><h2>Video evidence</h2><p className="caption">Clips cited for the latest answer.</p></div>
          <Badge>{relatedFootage.length}</Badge>
        </div>
        {relatedFootage.map((clip, index) => {
            const event = events.find((item) => item.id === clip.event_id);
            return <article className="evidence-card" key={`${clip.event_id}-${index}`}><Footage item={clip}/>{event && <button type="button" onClick={() => onOpen(event)}>View incident details <Icon name="chevron-right" size={16}/></button>}</article>;
          })}
      </aside>}
    </div>
    {historyOpen && <dialog ref={historyDialog} className="chat-history-drawer" aria-label="Past chats" onCancel={() => setHistoryOpen(false)} onClick={(e) => { if (e.target === historyDialog.current) setHistoryOpen(false); }}>
      <div className="chat-drawer-head"><div><p className="eyebrow">ASK SAFESPACE</p><h2>Past chats</h2></div><button type="button" className="circle" aria-label="Close past chats" onClick={() => setHistoryOpen(false)}>×</button></div>
      <div className="chat-drawer-list">{conversations.length ? conversations.map((item) => <button type="button" key={item.id} className={conversation === item.id ? 'selected' : ''} aria-current={conversation === item.id ? 'true' : undefined} onClick={() => { setHistoryOpen(false); void openConversation(item.id); }}><strong>{item.title}</strong><small>{item.message_count} messages</small></button>) : <p className="caption">Your conversations will appear here.</p>}</div>
    </dialog>}
    </>
  );
}
