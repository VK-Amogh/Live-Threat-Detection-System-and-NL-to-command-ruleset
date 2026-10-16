import type { ReactNode } from 'react';

const EVENT_ID = /(evt_[0-9a-f]{32})/g;

/** Inline formatting: **bold**, `code` and clickable incident ids. Never injects raw HTML. */
function inline(text: string, onEvent?: (id: string) => void): ReactNode[] {
  return text.split(/(\*\*[^*]+\*\*|`[^`]+`)/g).flatMap((part, i) => {
    if (part.startsWith('**') && part.endsWith('**')) return [<strong key={i}>{part.slice(2, -2)}</strong>];
    if (part.startsWith('`') && part.endsWith('`')) return [<code key={i}>{part.slice(1, -1)}</code>];
    return part.split(EVENT_ID).map((piece, j) => /^evt_[0-9a-f]{32}$/.test(piece)
      ? <button key={`${i}-${j}`} type="button" className="cite" onClick={() => onEvent?.(piece)} title={piece}>{piece.slice(0, 12)}…</button>
      : piece);
  });
}

export function Markdown({ text, onEvent }: { text: string; onEvent?: (id: string) => void }) {
  const blocks: ReactNode[] = [];
  let list: { ordered: boolean; items: string[] } | null = null;
  const flush = () => {
    if (!list) return;
    const Tag = list.ordered ? 'ol' : 'ul';
    blocks.push(<Tag key={blocks.length}>{list.items.map((item, i) => <li key={i}>{inline(item, onEvent)}</li>)}</Tag>);
    list = null;
  };
  for (const raw of text.split('\n')) {
    const line = raw.trimEnd();
    const bullet = /^\s*[-*•]\s+(.*)/.exec(line);
    const numbered = /^\s*\d+[.)]\s+(.*)/.exec(line);
    if (bullet || numbered) {
      const ordered = Boolean(numbered);
      if (list && list.ordered !== ordered) flush();
      list = list || { ordered, items: [] };
      list.items.push((bullet || numbered)![1]);
      continue;
    }
    flush();
    if (!line.trim()) continue;
    const heading = /^#{1,4}\s+(.*)/.exec(line);
    blocks.push(heading ? <h4 key={blocks.length}>{inline(heading[1], onEvent)}</h4> : <p key={blocks.length}>{inline(line, onEvent)}</p>);
  }
  flush();
  return <div className="markdown">{blocks}</div>;
}
