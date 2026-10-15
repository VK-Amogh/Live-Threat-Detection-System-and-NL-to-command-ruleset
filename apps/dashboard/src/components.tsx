import { useEffect, useRef, type ReactNode } from 'react';
import type { Incident } from './api/client';

export function Icon({ name, size = 20 }: { name: string; size?: number }) {
  return <img className="icon" src={`/icons/${name}.svg`} width={size} height={size} alt="" aria-hidden="true" />;
}
export function Empty({ title, children, icon = 'shield-check' }: { title: string; children: ReactNode; icon?: string }) {
  return <div className="empty"><div className="empty-icon"><Icon name={icon} size={40} /></div><h2>{title}</h2><p>{children}</p></div>;
}
export function Badge({ children }: { children: ReactNode }) { return <span className="badge">{children}</span>; }
export function ErrorNotice({ message }: { message: string | null }) { return message ? <div className="notice" role="alert"><Icon name="shield-01" />{message}</div> : null; }
export function Media({ incident }: { incident: Incident }) {
  const clip = incident.media?.find(m => m.kind === 'CLIP');
  const frame = incident.media?.find(m => m.kind === 'KEYFRAME');
  if (clip) return <video key={clip.url} controls preload="metadata" poster={frame?.url} src={clip.url}
    onLoadedMetadata={e => { e.currentTarget.currentTime = (clip.offset_ms || 0) / 1000; }} />;
  return frame ? <img className="evidence" src={frame.url} alt={`Evidence for ${incident.category.label}`} /> : <Empty title="No recording attached">This incident has metadata only.</Empty>;
}
export function Modal({ title, close, children }: { title: string; close: () => void; children: ReactNode }) {
  const ref = useRef<HTMLDialogElement>(null);
  useEffect(() => { ref.current?.showModal(); }, []);
  return <dialog ref={ref} className="modal" onCancel={close} onClick={e => { if (e.target === ref.current) close(); }}>
    <div className="section-head"><h2>{title}</h2><button className="circle" aria-label="Close" onClick={close}><Icon name="close" /></button></div>{children}
  </dialog>;
}
