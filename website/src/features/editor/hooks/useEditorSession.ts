import { useCallback, useEffect, useRef, useState } from 'react';
import {
  AuthError,
  SessionEndedError,
  ValidationError,
  VersionConflictError,
  editorApi,
} from '../api/client';
import { useAuthStore } from '../store/authStore';

interface State<T> {
  loading: boolean;
  content: T | null;
  sessionId: string | null;
  error: string | null;
  // Set to a user-friendly message when the session was killed by a
  // concurrent commit from another session (agent or other tab).
  externallyChanged: string | null;
  dirty: boolean;
  saving: boolean;
  committing: boolean;
}

export interface UseEditorSession<T> {
  loading: boolean;
  content: T | null;
  sessionId: string | null;
  error: string | null;
  externallyChanged: string | null;
  dirty: boolean;
  saving: boolean;
  committing: boolean;
  setContent: (updater: (prev: T) => T) => void;
  save: () => Promise<void>;
  saveAndCommit: () => Promise<void>;
  discard: () => Promise<void>;
}

/**
 * Opens a session, acquires the file, exposes the content for editing,
 * and commits on saveAndCommit(). Discards on unmount unless committed.
 *
 * Concurrency: the session is auto-dropped server-side if another session
 * commits the same file. A WebSocket on /events listens for
 * `session_discarded` matching our own id and flips `externallyChanged`
 * so the UI can show a banner. Any save/commit attempt after that point
 * surfaces SessionEndedError (404 → mapped in the client).
 */
export function useEditorSession<T = any>(
  fileName: string,
  label: string,
): UseEditorSession<T> {
  const [state, setState] = useState<State<T>>({
    loading: true,
    content: null,
    sessionId: null,
    error: null,
    externallyChanged: null,
    dirty: false,
    saving: false,
    committing: false,
  });
  const committedRef = useRef(false);

  const openSession = useCallback(async () => {
    setState((s) => ({
      ...s,
      loading: true,
      error: null,
      externallyChanged: null,
    }));
    try {
      const session = await editorApi.createSession(label);
      const res = await editorApi.acquire(session.id, fileName);
      setState({
        loading: false,
        content: res.content as T,
        sessionId: session.id,
        error: null,
        externallyChanged: null,
        dirty: false,
        saving: false,
        committing: false,
      });
    } catch (e: any) {
      if (e instanceof AuthError) {
        useAuthStore.getState().signOut();
        return;
      }
      setState((s) => ({ ...s, loading: false, error: e.message || 'errore sconosciuto' }));
    }
  }, [fileName, label]);

  useEffect(() => {
    openSession();
  }, [openSession]);

  // Keep a ref to state for cleanup + WS callbacks.
  const stateRef = useRef(state);
  useEffect(() => { stateRef.current = state; }, [state]);

  // Cleanup: discard on unmount if we opened a session and didn't commit.
  useEffect(() => {
    return () => {
      const sid = stateRef.current.sessionId;
      if (sid && !committedRef.current) {
        editorApi.discard(sid).catch(() => {});
      }
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  // WebSocket subscription: react to session_discarded events for our own
  // session id (fired when another session commits a file we had dirty).
  useEffect(() => {
    let ws: WebSocket | null = null;
    let closed = false;
    const connect = () => {
      if (closed) return;
      const proto = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
      ws = new WebSocket(`${proto}//${window.location.host}/events`);
      ws.onmessage = (msg) => {
        try {
          const frame = JSON.parse(msg.data);
          if (frame?.kind !== 'event' || !frame.event) return;
          const ev = frame.event;
          const ourSid = stateRef.current.sessionId;
          if (ev.type === 'session_discarded' && ourSid && ev.session_id === ourSid) {
            // Server auto-killed us because someone else committed. Swap
            // state — our local edits are now stranded.
            committedRef.current = true; // already gone server-side
            setState((s) => ({
              ...s,
              externallyChanged:
                'Il file è stato modificato da un\'altra sessione (l\'agente o un\'altra scheda). Le modifiche locali sono state scartate.',
              sessionId: null,
              dirty: false,
            }));
          }
        } catch { /* ignore malformed frames */ }
      };
      ws.onclose = () => {
        if (!closed) setTimeout(connect, 2000);
      };
    };
    connect();
    return () => {
      closed = true;
      ws?.close();
    };
  }, []);

  const setContent = useCallback((updater: (prev: T) => T) => {
    setState((s) => {
      if (s.content == null) return s;
      return { ...s, content: updater(s.content), dirty: true };
    });
  }, []);

  const save = useCallback(async () => {
    const { sessionId, content } = stateRef.current;
    if (!sessionId || content == null) return;
    setState((s) => ({ ...s, saving: true, error: null }));
    try {
      await editorApi.putFile(sessionId, fileName, content);
      setState((s) => ({ ...s, saving: false, dirty: false }));
    } catch (e: any) {
      if (e instanceof AuthError) {
        useAuthStore.getState().signOut();
        throw e;
      }
      if (e instanceof SessionEndedError) {
        setState((s) => ({
          ...s,
          saving: false,
          externallyChanged:
            'La sessione è stata chiusa (il file è stato modificato altrove).',
          sessionId: null,
        }));
        committedRef.current = true;
        throw e;
      }
      if (e instanceof ValidationError) {
        setState((s) => ({ ...s, saving: false, error: `Validazione fallita: ${e.detail}` }));
      } else {
        setState((s) => ({ ...s, saving: false, error: e.message || 'salvataggio fallito' }));
      }
      throw e;
    }
  }, [fileName]);

  const saveAndCommit = useCallback(async () => {
    await save();
    const { sessionId } = stateRef.current;
    if (!sessionId) return;
    setState((s) => ({ ...s, committing: true }));
    try {
      await editorApi.commit(sessionId);
      committedRef.current = true;
      setState((s) => ({ ...s, committing: false, dirty: false }));
    } catch (e: any) {
      if (e instanceof VersionConflictError || e instanceof SessionEndedError) {
        committedRef.current = true;
        setState((s) => ({
          ...s,
          committing: false,
          externallyChanged:
            'Il file è stato modificato altrove mentre stavi salvando. Le modifiche non sono state applicate.',
          sessionId: null,
        }));
        throw e;
      }
      setState((s) => ({ ...s, committing: false, error: e.message || 'commit fallito' }));
      throw e;
    }
  }, [save]);

  const discard = useCallback(async () => {
    const { sessionId } = stateRef.current;
    committedRef.current = true;
    if (sessionId) {
      try {
        await editorApi.discard(sessionId);
      } catch {}
    }
    setState((s) => ({ ...s, sessionId: null, dirty: false }));
  }, []);

  return {
    ...state,
    setContent,
    save,
    saveAndCommit,
    discard,
  };
}
