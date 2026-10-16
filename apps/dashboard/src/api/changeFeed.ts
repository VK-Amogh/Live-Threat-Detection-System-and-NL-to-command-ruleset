import { useEffect, useState } from 'react';
import { api, post, type Incident } from './client';

type ChangePage = { items: Incident[]; next_after: number; has_more: boolean; head_seq: number };

const key = 'safespace.changeSeq';

export function useChangeFeed(enabled: boolean, onEvent: (event: Incident) => void, onSource: () => void) {
  const [connected, setConnected] = useState(false);
  useEffect(() => {
    if (!enabled) return;
    let stopped = false;
    let socket: WebSocket | undefined;
    let timer: number | undefined;
    let attempts = 0;
    let cursor = 0;
    try { cursor = Number(localStorage.getItem(key)) || 0; } catch { /* storage unavailable */ }
    let draining = false;
    let again = false;

    async function catchUp() {
      if (draining) { again = true; return; }
      draining = true;
      let failed = false;
      try {
        do {
          again = false;
          const page = await api<ChangePage>(`/changes?after=${cursor}&limit=200`);
          if (page.head_seq < cursor) { cursor = 0; again = true; continue; }
          for (const item of page.items) {
            if (item.change_seq <= cursor) continue;
            cursor = item.change_seq;
            onEvent(item);
          }
          try { localStorage.setItem(key, String(cursor)); } catch { /* storage unavailable */ }
          if (page.has_more) again = true;
        } while (again && !stopped);
      } catch { failed = true; /* reconnect and next poll will retry from the last committed sequence */ }
      finally { draining = false; if (again && !failed && !stopped) void catchUp(); }
    }

    async function connect() {
      try {
        const ticket = await post<{ticket: string}>('/ws-tickets');
        if (stopped) return;
        socket = new WebSocket(`${location.protocol === 'https:' ? 'wss' : 'ws'}://${location.host}/api/v1/ws?ticket=${encodeURIComponent(ticket.ticket)}`);
        socket.onopen = () => { attempts = 0; setConnected(true); void catchUp(); };
        socket.onmessage = message => {
          const envelope = JSON.parse(message.data);
          if (envelope.type === 'ping') socket?.send(JSON.stringify({type: 'pong'}));
          if (envelope.type === 'hello' && envelope.data?.head_seq < cursor) { cursor = 0; void catchUp(); }
          if (typeof envelope.type === 'string' && envelope.type.startsWith('event.')) void catchUp();
          if (envelope.type === 'source.updated') onSource();
        };
        socket.onclose = () => {
          setConnected(false);
          if (!stopped) timer = window.setTimeout(connect, Math.min(30000, 1000 * 2 ** attempts++));
        };
      } catch {
        if (!stopped) timer = window.setTimeout(connect, 5000);
      }
    }

    void connect();
    const poll = window.setInterval(() => void catchUp(), 5000);
    return () => { stopped = true; clearInterval(poll); clearTimeout(timer); socket?.close(); setConnected(false); };
  }, [enabled, onEvent, onSource]);
  return connected;
}
