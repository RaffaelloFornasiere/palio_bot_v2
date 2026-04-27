import { create } from 'zustand';
import { User } from 'firebase/auth';
import {
  initFirebase,
  signInWithGoogle,
  signOutGoogle,
  onAuthChange,
} from '../api/firebase';

interface AuthState {
  initialized: boolean;
  authRequired: boolean | null;
  firebaseConfigured: boolean;
  user: User | null;
  loading: boolean;
  error: string | null;
  init: () => Promise<void>;
  signIn: () => Promise<void>;
  signOut: () => Promise<void>;
  clearError: () => void;
}

let unsub: (() => void) | null = null;

export const useAuthStore = create<AuthState>((set, get) => ({
  initialized: false,
  authRequired: null,
  firebaseConfigured: false,
  user: null,
  loading: false,
  error: null,

  async init() {
    if (get().initialized) return;
    try {
      const cfg = await initFirebase();
      set({
        authRequired: cfg.auth_required,
        firebaseConfigured: !!cfg.firebase,
      });
      if (cfg.firebase) {
        if (unsub) unsub();
        // Wait for the first onAuthStateChanged callback before marking
        // the store initialized — Firebase restores its persisted session
        // asynchronously, and completing init too early causes a blank
        // flash / spurious redirect to /edit/login on the first load.
        await new Promise<void>((resolve) => {
          let resolved = false;
          unsub = onAuthChange((user) => {
            set({ user });
            if (!resolved) {
              resolved = true;
              resolve();
            }
          });
        });
      }
      set({ initialized: true });
    } catch (e: any) {
      set({ error: e?.message || 'init failed', initialized: true });
    }
  },

  async signIn() {
    set({ loading: true, error: null });
    try {
      await signInWithGoogle();
      // onAuthChange callback will populate `user`.
      set({ loading: false });
    } catch (e: any) {
      const msg =
        e?.code === 'auth/popup-closed-by-user'
          ? 'Accesso annullato.'
          : e?.message || 'Accesso fallito';
      set({ loading: false, error: msg });
    }
  },

  async signOut() {
    await signOutGoogle();
    set({ user: null });
  },

  clearError() {
    set({ error: null });
  },
}));

export function isAuthenticated(s: AuthState): boolean {
  // In dev-mode (no auth configured), everyone is "authenticated".
  if (s.authRequired === false) return true;
  return !!s.user;
}
