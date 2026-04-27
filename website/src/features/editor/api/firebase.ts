import { initializeApp, FirebaseApp } from 'firebase/app';
import {
  getAuth,
  GoogleAuthProvider,
  signInWithPopup,
  signInWithRedirect,
  getRedirectResult,
  signOut,
  onAuthStateChanged,
  User,
  Auth,
} from 'firebase/auth';
import { getApiBaseUrl } from '../../../utils/api';

export interface EditorBootConfig {
  auth_required: boolean;
  firebase: null | {
    projectId: string;
    apiKey: string;
    authDomain: string;
    appId?: string | null;
  };
}

let appInstance: FirebaseApp | null = null;
let authInstance: Auth | null = null;
let initPromise: Promise<EditorBootConfig> | null = null;

export async function loadEditorConfig(): Promise<EditorBootConfig> {
  const res = await fetch(`${getApiBaseUrl()}/api/editor/config`);
  if (!res.ok) throw new Error(`config fetch failed: ${res.status}`);
  return (await res.json()) as EditorBootConfig;
}

export async function initFirebase(): Promise<EditorBootConfig> {
  if (initPromise) return initPromise;
  initPromise = (async () => {
    const cfg = await loadEditorConfig();
    if (cfg.firebase && !appInstance) {
      appInstance = initializeApp({
        apiKey: cfg.firebase.apiKey,
        authDomain: cfg.firebase.authDomain,
        projectId: cfg.firebase.projectId,
        appId: cfg.firebase.appId ?? undefined,
      });
      authInstance = getAuth(appInstance);
      // Finish redirect flow if we just came back from the Google page.
      try { await getRedirectResult(authInstance); } catch { /* ignore */ }
    }
    return cfg;
  })();
  return initPromise;
}

export function getFirebaseAuth(): Auth | null {
  return authInstance;
}

export async function signInWithGoogle(): Promise<User> {
  const auth = authInstance;
  if (!auth) throw new Error('Firebase not initialized');
  const provider = new GoogleAuthProvider();
  provider.setCustomParameters({ prompt: 'select_account' });
  try {
    const res = await signInWithPopup(auth, provider);
    return res.user;
  } catch (e: any) {
    // Popup blocked on some mobile browsers — fall back to redirect.
    if (e?.code === 'auth/popup-blocked' || e?.code === 'auth/operation-not-supported-in-this-environment') {
      await signInWithRedirect(auth, provider);
      return new Promise(() => {}); // redirect takes over
    }
    throw e;
  }
}

export async function signOutGoogle(): Promise<void> {
  if (authInstance) await signOut(authInstance);
}

export function onAuthChange(cb: (user: User | null) => void): () => void {
  if (!authInstance) {
    cb(null);
    return () => {};
  }
  return onAuthStateChanged(authInstance, cb);
}

export async function getIdToken(): Promise<string | null> {
  const user = authInstance?.currentUser;
  if (!user) return null;
  return user.getIdToken(/* forceRefresh */ false);
}
