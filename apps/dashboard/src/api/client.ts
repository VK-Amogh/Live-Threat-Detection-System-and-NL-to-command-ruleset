import type { components } from './generated/schema';

export type Incident = components['schemas']['EventOut'];
export type Source = components['schemas']['SourceRecord'];
export type Camera = components['schemas']['CameraOut'];
export type System = components['schemas']['SystemSnapshot'];
export type Settings = components['schemas']['RuntimeSettings'];

export async function api<T>(path: string, options: RequestInit = {}): Promise<T> {
  const response = await fetch(`/api/v1${path}`, { credentials: 'include', ...options,
    headers: { ...(options.body && !(options.body instanceof FormData) ? { 'Content-Type': 'application/json' } : {}), ...options.headers } });
  if (!response.ok) {
    const data = await response.json().catch(() => ({}));
    if (response.status === 401) window.dispatchEvent(new Event('session-expired'));
    throw new Error(typeof data.detail === 'string' ? data.detail : `Request failed (${response.status})`);
  }
  return response.json();
}
export const post = <T,>(path: string, body?: unknown) => api<T>(path, { method: 'POST', body: body === undefined ? undefined : JSON.stringify(body) });
export function date(value: string) { return new Date(value).toLocaleString(undefined, { dateStyle: 'medium', timeStyle: 'short' }); }
