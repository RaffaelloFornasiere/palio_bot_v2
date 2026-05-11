import { getApiBaseUrl } from '../../../utils/api';
import { getIdToken } from './firebase';

export class AuthError extends Error {
  constructor(message = 'not authenticated') {
    super(message);
  }
}

export class VersionConflictError extends Error {
  constructor(public file: string) {
    super(`il file ${file} è stato modificato nel frattempo`);
  }
}

export class SessionEndedError extends Error {
  constructor() {
    super('la sessione è terminata');
  }
}

export class ValidationError extends Error {
  constructor(public detail: string) {
    super(detail);
  }
}

async function request<T = any>(
  path: string,
  options: RequestInit = {},
): Promise<T> {
  const headers = new Headers(options.headers);
  headers.set('Content-Type', 'application/json');
  const token = await getIdToken();
  if (token) headers.set('Authorization', `Bearer ${token}`);

  const res = await fetch(`${getApiBaseUrl()}${path}`, { ...options, headers });

  if (res.status === 401) {
    throw new AuthError();
  }

  const text = await res.text();
  const body = text ? JSON.parse(text) : {};

  if (res.status === 409) {
    const d = body.detail ?? body;
    if (d && typeof d === 'object' && d.error === 'version_conflict') {
      throw new VersionConflictError(d.file);
    }
  }
  if (res.status === 404 && path.includes('/api/sessions/')) {
    // Session no longer exists — was auto-discarded after another commit,
    // or it simply expired.
    throw new SessionEndedError();
  }
  if (res.status === 422) {
    const msg = typeof body.detail === 'string' ? body.detail : JSON.stringify(body.detail);
    throw new ValidationError(msg);
  }
  if (!res.ok) {
    const msg = typeof body.detail === 'string' ? body.detail : `HTTP ${res.status}`;
    throw new Error(msg);
  }
  return body as T;
}

export const editorApi = {
  async me(): Promise<void> {
    await request('/api/editor/me');
  },

  async createSession(label: string) {
    return request<{ id: string; label: string; created_at: string }>(
      '/api/sessions',
      { method: 'POST', body: JSON.stringify({ label }) },
    );
  },

  async listSessions() {
    return request<{ sessions: Array<{ id: string; label: string; files_held: string[] }> }>(
      '/api/sessions',
    );
  },

  async acquire(sessionId: string, fileName: string) {
    return request<{ content: any; version: string }>(
      `/api/sessions/${sessionId}/acquire/${fileName}`,
      { method: 'POST' },
    );
  },

  async putFile(sessionId: string, fileName: string, content: unknown) {
    return request<{ version: string }>(
      `/api/sessions/${sessionId}/files/${fileName}`,
      { method: 'PUT', body: JSON.stringify({ content }) },
    );
  },

  async commit(sessionId: string) {
    return request<{ files: Record<string, string> }>(
      `/api/sessions/${sessionId}/commit`,
      { method: 'POST' },
    );
  },

  async discard(sessionId: string) {
    return request<{ ok: boolean }>(
      `/api/sessions/${sessionId}/discard`,
      { method: 'POST' },
    );
  },

  async readFile<T = any>(fileName: string): Promise<T> {
    return request<T>(`/api/files/${fileName}`);
  },

  async previewLeaderboard() {
    return request<{
      proposed: any;
      changed_games: Array<{ id: string; name: string }>;
    }>('/api/leaderboard/preview', { method: 'POST' });
  },

  async applyLeaderboard(proposed: any) {
    return request<{ status: string; version: string }>(
      '/api/leaderboard/apply',
      { method: 'POST', body: JSON.stringify({ proposed }) },
    );
  },
};
