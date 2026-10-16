import { useEffect, useRef, useState, type FormEvent } from 'react';
import type { Incident, System } from '../api/client';
import { Badge, Empty, ErrorNotice, Icon, Media } from '../components';
import { Markdown } from '../markdown';

type Cited = { event_id: string; label: string; clip_url: string | null; start_ms: number; poster_url: string | null };
type Message = { role: 'user' | 'assistant'; text: string; eventIds: string[]; cited: Cited[]; status?: string; model?: string };

const PROMPTS = ['Summarize the most recent incident and what the footage shows.', 'Which incidents still need review?', 'Show me the footage of the highest-severity incident.', 'How many incidents were detected by category?'];

function Footage({ item }: { item: Cited }) {
  if (!item.clip_url) return item.poster_url ? <img className="evidence" src={item.poster_url} alt={`Evidence for ${item.label}`} /> : null;
  return <figure className="footage"><video controls preload="metadata" poster={item.poster_url || undefined} src={item.clip_url}
    onLoadedMetadata={e => { e.currentTarget.currentTime = item.start_ms / 1000; }} /><figcaption>{item.label} · playback starts just before the detection</figcaption></figure>;
}

export function Investigation({ events, scope, setScope, onOpen, system }: { events: Incident[]; scope: string | null; setScope: (id: string | null) => void; onOpen: (e: Incident) => void; system: System | null }) {
  const [messages, setMessages] = useState<Message[]>([]);
  const [input, setInput] = useState('');
  const [provider, setProvider] = useState<'ollama' | 'groq'>('ollama');
  const [images, setImages] = useState(true);
  const [conversation, setConversation] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [refs, setRefs] = useState<string[]>([]);
  const abort = useRef<AbortController>();
  const end = useRef<HTMLDivElement>(null);
  const groq = Boolean(system?.chat.groq_configured);
  useEffect(() => { if (groq) setProvider(String(system?.chat.chat_provider) === 'groq' ? 'groq' : 'ollama'); }, [groq, system?.chat.chat_provider]);
  useEffect(() => { end.current?.scrollIntoView({ behavior: 'smooth', block: 'end' }); }, [messages]);

  const patch = (change: (m: Message) => Message) => setMessages(old => old.map((m, i) => (i === old.length - 1 ? change(m) : m)));
  const openEvent = (id: string) => { const found = events.find(e => e.id === id); if (found) onOpen(found); };

  async function ask(question: string) {
    if (!question.trim() || busy) return;
    setInput(''); setBusy(true); setError(null);
    setMessages(old => [...old, { role: 'user', text: question, eventIds: [], cited: [] }, { role: 'assistant', text: '', eventIds: [], cited: [], status: 'Searching incident records…' }]);
    abort.current = new AbortController();
    try {
      const response = await fetch('/api/v1/chat/stream', { method: 'POST', credentials: 'include', signal: abort.current.signal, headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ message: question, conversation_id: conversation, provider, event_ids: scope ? [scope] : [], include_images: images }) });
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
          if (item.type === 'context') { setRefs(item.event_ids); setConversation(item.conversation_id); patch(m => ({ ...m, eventIds: item.event_ids, model: item.model, status: 'Reading evidence…' })); }
          if (item.type === 'status') patch(m => ({ ...m, status: item.message }));
          if (item.type === 'delta') patch(m => ({ ...m, text: m.text + item.text, status: undefined }));
          if (item.type === 'done') patch(m => ({ ...m, cited: item.cited || [], status: undefined }));
        }
      }
    } catch (e) {
      if ((e as Error).name !== 'AbortError') setError((e as Error).message);
    } finally { setBusy(false); abort.current = undefined; patch(m => ({ ...m, status: undefined })); }
  }
  const submit = (e: FormEvent) => { e.preventDefault(); void ask(input.trim()); };

  return <div className="chat-layout"><section className="panel chat-panel">
    <div className="chat-toolbar">
      <select aria-label="Chat provider" value={provider} onChange={e => setProvider(e.target.value as 'ollama' | 'groq')}>
        <option value="ollama">Local · {String(system?.chat.ollama_model || 'Gemma')}</option>
        <option value="groq" disabled={!groq}>Groq · {String(system?.chat.groq_model || 'Qwen')}</option>
      </select>
      <select aria-label="Incident scope" value={scope || ''} onChange={e => { setScope(e.target.value || null); setConversation(null); setMessages([]); }}>
        <option value="">All recent incidents</option>{events.map(e => <option key={e.id} value={e.id}>{e.category.label} · {e.camera.name}</option>)}
      </select>
    </div>
    <p className="caption">{provider === 'groq' ? 'Your question, incident metadata and the selected evidence frames are sent to Groq. Full recordings stay on your PC.' : 'Everything — questions, metadata and evidence frames — stays on your PC.'}</p>
    <label className="checkbox"><input type="checkbox" checked={images} onChange={e => setImages(e.target.checked)} />Let the assistant look at evidence frames from the footage</label>
    <div className="messages" aria-live="polite">
      {messages.length ? messages.map((m, i) => <div className={`message ${m.role}`} key={i}>
        <span className="eyebrow">{m.role === 'user' ? 'YOU' : `SAFESPACE${m.model ? ' · ' + m.model : ''}`}</span>
        {m.role === 'user' ? <p>{m.text}</p> : <>
          {m.text ? <Markdown text={m.text} onEvent={openEvent} /> : <p className="status-line">{m.status || (busy ? 'Connecting to the model…' : 'No response received.')}</p>}
          {m.status && m.text && <p className="status-line">{m.status}</p>}
          {m.cited.map(c => <Footage key={c.event_id} item={c} />)}
        </>}
      </div>) : <Empty title="The story is in the evidence." icon="search-01">Ask what happened, which detections need review, or to see the recording of an incident. The assistant reads the detector output and looks at the footage.
        <span className="prompt-chips">{PROMPTS.map(p => <button key={p} type="button" onClick={() => void ask(p)}>{p}</button>)}</span></Empty>}
      <div ref={end} />
    </div>
    <ErrorNotice message={error} />
    <form className="chat-composer" onSubmit={submit}>
      <textarea aria-label="Ask about incidents" rows={2} placeholder="What happened in the most recent incident?" value={input} maxLength={4000} onChange={e => setInput(e.target.value)}
        onKeyDown={e => { if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); e.currentTarget.form?.requestSubmit(); } }} />
      {busy ? <button type="button" onClick={() => abort.current?.abort()}><Icon name="pause-01" />Stop</button>
        : <button className="primary" disabled={!input.trim()} aria-label="Send question"><Icon name="search-01" />Ask</button>}
    </form>
  </section>
    <aside className="panel"><div className="section-head"><h2>Evidence desk</h2><Badge>{refs.length}</Badge></div>
      {refs.length ? refs.slice(0, 6).map(id => { const e = events.find(x => x.id === id); return e ? <article className="evidence-card" key={id}><Media incident={e} /><h3>{e.category.label}</h3><p>{e.camera.name}</p><button onClick={() => onOpen(e)}>Open incident<Icon name="link-external" /></button></article> : null; })
        : <Empty title="Sources appear here" icon="video-on">Referenced images and recordings stay beside the conversation.</Empty>}
    </aside></div>;
}
