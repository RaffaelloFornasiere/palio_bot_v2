// Best-effort device identity for the borgo poll: a random UUID kept in
// localStorage. NOT authentication — it only stops casual revoting from
// the same browser. Real flood resistance is Cloudflare Turnstile on the
// backend. Survives reloads; resets if the user clears storage / uses a
// different browser or incognito (acceptable for a popularity poll).

const KEY = 'palio_poll_client_id';

export function getClientId(): string {
  let id: string | null = null;
  try {
    id = localStorage.getItem(KEY);
  } catch {
    /* storage blocked (private mode strict): fall back to a volatile id */
  }
  if (id && id.length >= 8) return id;

  const fresh =
    typeof crypto !== 'undefined' && 'randomUUID' in crypto
      ? crypto.randomUUID()
      : 'fb-' + Math.random().toString(36).slice(2) + Date.now().toString(36);

  try {
    localStorage.setItem(KEY, fresh);
  } catch {
    /* unwritable: the id stays in-memory for this page load only */
  }
  return fresh;
}
