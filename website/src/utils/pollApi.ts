// Thin fetch client for the public borgo poll endpoints. Uses relative
// paths (same-origin) so it works behind the Cloudflare tunnel via the
// CRA dev proxy / FastAPI catch-all — no CORS gymnastics, same as the
// rest of the app.
import { getApiBaseUrl } from './api';

export interface PollStats {
  today: string;
  today_counts: Record<string, number>;
  today_votes: number;
  total_counts: Record<string, number>;
  total_votes: number;
}

export interface PollStatus {
  ever_voted: boolean;
  voted_today: boolean;
}

export type VoteOutcome = 'recorded' | 'already_voted';

export interface VoteResult {
  status: VoteOutcome;
  day: string;
  stats: PollStats;
}

const base = () => getApiBaseUrl();

export async function getPollStatus(clientId: string): Promise<PollStatus> {
  const r = await fetch(
    `${base()}/api/poll/status?client_id=${encodeURIComponent(clientId)}`,
  );
  if (!r.ok) throw new Error(`status ${r.status}`);
  return r.json();
}

export async function getPollStats(): Promise<PollStats> {
  const r = await fetch(`${base()}/api/poll/stats`);
  if (!r.ok) throw new Error(`stats ${r.status}`);
  return r.json();
}

export async function castVote(args: {
  clientId: string;
  borgo: string;
  turnstileToken: string | null;
}): Promise<VoteResult> {
  const r = await fetch(`${base()}/api/poll/vote`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      client_id: args.clientId,
      borgo: args.borgo,
      turnstile_token: args.turnstileToken,
    }),
  });
  if (r.status === 403) {
    throw new Error('Verifica anti-bot non superata. Riprova.');
  }
  if (!r.ok) {
    let detail = `errore ${r.status}`;
    try {
      const body = await r.json();
      if (body?.detail) detail = String(body.detail);
    } catch {
      /* non-JSON error body */
    }
    throw new Error(detail);
  }
  return r.json();
}
