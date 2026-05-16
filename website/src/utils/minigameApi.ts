// Thin fetch client for the goliardic mini-games scoreboard. Same
// same-origin / relative-path approach as pollApi.ts so it works behind
// the Cloudflare tunnel without CORS gymnastics.
import { getApiBaseUrl } from './api';

export type MiniGameId = 'dino' | 'bros' | 'reazione' | 'sequenza' | 'flappy';

export interface GameRankRow {
  borgo: string;
  score: number;
  position: number;
  points: number;
}

export interface OverallRow {
  borgo: string;
  points: number;
  position: number;
  by_game: Record<string, number>;
}

export interface MiniGamePodium {
  games: Record<string, { label: string; ranking: GameRankRow[] }>;
  overall: OverallRow[];
}

const base = () => getApiBaseUrl();

export async function getMiniGamePodium(): Promise<MiniGamePodium> {
  const r = await fetch(`${base()}/api/minigame/podium`);
  if (!r.ok) throw new Error(`podium ${r.status}`);
  return r.json();
}

// Fire-and-forget: a failed score submission must never disrupt play.
export async function submitMiniGameScore(args: {
  game: MiniGameId;
  borgo: string;
  score: number;
}): Promise<void> {
  try {
    await fetch(`${base()}/api/minigame/score`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        game: args.game,
        borgo: args.borgo,
        score: Math.max(0, Math.floor(args.score)),
      }),
    });
  } catch {
    /* ignore — goliardic, not worth bothering the player */
  }
}
