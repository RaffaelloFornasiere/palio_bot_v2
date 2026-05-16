import React, { useEffect, useRef, useState } from 'react';
import {
  Container, Card, CardContent, Box, Typography, IconButton, Button,
  Stack, CircularProgress, Alert, useTheme,
} from '@mui/material';
import { alpha } from '@mui/material/styles';
import ChevronLeftIcon from '@mui/icons-material/ChevronLeft';
import ChevronRightIcon from '@mui/icons-material/ChevronRight';
import ReplayIcon from '@mui/icons-material/Replay';
import { Leaderboard, PalioData } from '../../../generated/types.gen';
import { getLeaderboardDataForYear, getPalioDataForYear } from '../../../utils/yearApi';
import { useYear } from '../../../contexts/YearContext';
import { hexToRgb, curatedVillageColor } from '../../../utils/colorUtils';
import { MASCOTS, FALLBACK_EMOJI } from '../../../utils/villages';
import { Link as RouterLink } from 'react-router-dom';
import YearSelector from '../../../components/YearSelector';
import { getPollStats } from '../../../utils/pollApi';
import './MascotRace.css';

/* Animated leaderboard replay. MUI shell + a custom race field/podium
   themed from the MUI theme. The 60fps engine is imperative (refs + rAF)
   so there are no per-frame re-renders. Data is real: each game's
   `overall_leaderboard` already sums that game's per-division points, so
   the cumulative sum of `overall_leaderboard` across every scheduled game
   reproduces `palio_leaderboard` exactly — no averaging, no anchoring.
   The track spans all games in palio.json, not only the played ones. */

const MEDALS       = ['🥇', '🥈', '🥉', '4°', '5°'];
const RANK_TO_SLOT = [2, 1, 3, 0, 4];                 // Olympic order 4·2·1·3·5
const HEIGHTS      = [1.0, 0.76, 0.57, 0.40, 0.28];
const SLOT_PLACE   = [4, 2, 1, 3, 5];

const MOVE_MS = 650;
const HOLD_MS = 470;

const lerp = (a: number, b: number, t: number) => a + (b - a) * t;

function textOn(hex: string): string {
  const rgb = hexToRgb(hex);
  if (!rgb) return '#fff';
  const l = (0.299 * rgb.r + 0.587 * rgb.g + 0.114 * rgb.b) / 255;
  return l > 0.6 ? '#000' : '#fff';
}

interface RaceData {
  villages: string[];
  colors: Record<string, string>;
  series: Record<string, number[]>;   // cumulative points, index 0..totalGames
  gameNames: string[];                // index 0 = "Partenza"
  steps: number;                      // games with results — animate/count to here
  totalGames: number;                 // all scheduled games — "/ N" + track ceiling
}

// Build the cumulative per-village series over every scheduled game.
// `overall_leaderboard` for a game already sums that game's per-division
// points, so the running sum of `overall_leaderboard` reproduces
// `palio_leaderboard` exactly — no division averaging, no final anchor.
// Games are ordered by calendar date (palio.json array order is NOT
// execution order); only games that have results become keyframes, so
// the counter reads completed-count / total-scheduled and the animation
// steps through exactly the games played, skipping the missing ones.
const startOf = (dates?: Array<{ start_datetime?: string | null }>): number => {
  const ts = (dates || [])
    .map((d) => Date.parse(d.start_datetime || ''))
    .filter((n) => !Number.isNaN(n));
  return ts.length ? Math.min(...ts) : Number.MAX_SAFE_INTEGER;
};

function buildRaceData(lb: Leaderboard, palio: PalioData): RaceData {
  const villages = (palio.villages?.length ? palio.villages : lb.villages).slice();
  const rawColors = palio.villages_colors || {};
  const colors: Record<string, string> = {};
  villages.forEach((v) => { colors[v] = curatedVillageColor(rawColors[v] || '#888888'); });

  // Every scheduled game, sorted by when it is actually played.
  const scheduled = (palio.games?.length
    ? palio.games.map((g) => ({ id: g.id, name: g.name, t: startOf(g.dates) }))
    : Object.keys(lb.game_leaderboards).sort().map((id, i) => ({
        id, name: lb.game_leaderboards[id].game_name || id, t: i,
      }))
  ).sort((a, b) => a.t - b.t || a.id.localeCompare(b.id));
  const totalGames = scheduled.length;

  // Keyframes = only the games that have results, in calendar order.
  const played = scheduled.filter((g) => {
    const ov = lb.game_leaderboards[g.id]?.overall_leaderboard;
    return ov && Object.keys(ov).length > 0;
  });

  const cum: Record<string, number> = {};
  const series: Record<string, number[]> = {};
  villages.forEach((v) => { cum[v] = 0; series[v] = [0]; });
  for (const g of played) {
    const ov = lb.game_leaderboards[g.id]?.overall_leaderboard || {};
    villages.forEach((v) => { cum[v] += ov[v]?.points || 0; series[v].push(cum[v]); });
  }

  const gameNames = ['Partenza', ...played.map((g) => g.name)];
  return { villages, colors, series, gameNames, steps: played.length, totalGames };
}

const MascotRace: React.FC = () => {
  const theme = useTheme();
  const { selectedYear } = useYear();

  const [data, setData] = useState<RaceData | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  // The borgo currently leading the popularity poll. Gets a ❤ on its
  // podium token that links to the (nav-less) daily voting page — the
  // intentional "why does that borgo have a heart?" hook.
  const [lovedBorgo, setLovedBorgo] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    getPollStats()
      .then((s) => {
        if (cancelled) return;
        const entries = Object.entries(s.total_counts || {});
        if (!entries.length) return;
        entries.sort((a, b) => b[1] - a[1] || a[0].localeCompare(b[0]));
        if (entries[0][1] > 0) setLovedBorgo(entries[0][0]);
      })
      .catch(() => {/* poll off/unreachable — just no heart */});
    return () => { cancelled = true; };
  }, []);

  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        setLoading(true);
        setError(null);
        const [lbRes, palioRes] = await Promise.all([
          getLeaderboardDataForYear(selectedYear),
          getPalioDataForYear(selectedYear),
        ]);
        if (lbRes.error || palioRes.error) throw new Error('Failed to fetch data');
        if (!cancelled) setData(buildRaceData(lbRes.data!, palioRes.data!));
      } catch (err) {
        if (!cancelled) setError(err instanceof Error ? err.message : 'An error occurred');
      } finally {
        if (!cancelled) setLoading(false);
      }
    })();
    return () => { cancelled = true; };
  }, [selectedYear]);

  // ---- imperative animation engine (rebuilt whenever data changes) --------
  const tokenRefs  = useRef<Record<string, HTMLDivElement | null>>({});
  const ptsRefs    = useRef<Record<string, HTMLSpanElement | null>>({});
  const deltaRefs  = useRef<Record<string, HTMLSpanElement | null>>({});
  const crownRefs  = useRef<Record<string, HTMLSpanElement | null>>({});
  const tokRefs    = useRef<Record<string, HTMLDivElement | null>>({});
  const tokPtsRefs = useRef<Record<string, HTMLSpanElement | null>>({});
  const podiumRef  = useRef<HTMLDivElement | null>(null);
  const dayNRef    = useRef<HTMLSpanElement | null>(null);
  const dayLabelRef = useRef<HTMLSpanElement | null>(null);

  const rafRef      = useRef<number | null>(null);
  const startTsRef  = useRef<number | null>(null);
  const elapsedRef  = useRef(0);
  const lastGameRef = useRef(0);
  const apiRef = useRef<{ jump: (d: number) => void; replay: () => void } | null>(null);

  useEffect(() => {
    if (!data) return;
    const { villages, series, gameNames } = data;
    const STEPS = data.steps;
    const MAXPTS = data.totalGames * 10 + 10;   // rule ceiling, all games — fixed scale
    const posPct = (p: number) => (p / MAXPTS) * 100;

    const perGame = () => MOVE_MS + HOLD_MS;
    const totalMs = () => STEPS * perGame();

    const fOf = (ms: number) => {
      const pg = perGame(), k = Math.floor(ms / pg);
      if (k >= STEPS) return STEPS;
      const rem = ms - k * pg;
      return rem < MOVE_MS ? k + rem / MOVE_MS : k + 1;
    };
    const msOf = (f: number) => {
      if (f <= 0) return 0;
      if (f >= STEPS) return totalMs();
      const g = Math.floor(f), frac = f - g, pg = perGame();
      return frac > 1e-9 ? g * pg + frac * MOVE_MS : (g - 1) * pg + MOVE_MS;
    };

    const renderAt = (fRaw: number, flash: boolean) => {
      const f = Math.max(0, Math.min(STEPS, fRaw));
      const lo = Math.floor(f), hi = Math.min(lo + 1, STEPS), fr = f - lo;

      const pts: Record<string, number> = {};
      let lead = -1, leader: string | null = null;
      for (const v of villages) {
        const p = lerp(series[v][lo], series[v][hi], fr);
        pts[v] = p;
        const tk = tokenRefs.current[v];
        if (tk) tk.style.left = posPct(p) + '%';
        const pe = ptsRefs.current[v];
        if (pe) pe.textContent = String(Math.round(p));
        if (p > lead) { lead = p; leader = v; }
      }
      for (const v of villages) {
        const cr = crownRefs.current[v];
        if (cr) cr.classList.toggle('on', v === leader && f > 0);
      }

      if (podiumRef.current) podiumRef.current.classList.toggle('pre', f === 0);

      const ranked = villages.map((v, i) => ({ v, p: pts[v], i }))
        .sort((a, z) => z.p - a.p || a.i - z.i);
      ranked.forEach((e, rank) => {
        const slot = RANK_TO_SLOT[rank] ?? rank;
        const t = tokRefs.current[e.v];
        if (t) {
          t.style.left   = `calc(${slot} * 20% + 10%)`;
          t.style.bottom = `calc(var(--podH) * ${HEIGHTS[rank] ?? 0.2} + 30px)`;
        }
        const tp = tokPtsRefs.current[e.v];
        if (tp) tp.textContent = String(Math.round(e.p));
      });

      const reached = Math.floor(f + 1e-6);
      if (flash) {
        while (lastGameRef.current < reached) {
          lastGameRef.current++;
          for (const v of villages) {
            const gain = series[v][lastGameRef.current] - series[v][lastGameRef.current - 1];
            if (gain > 0.5) {
              const el = deltaRefs.current[v];
              if (el) {
                el.textContent = '+' + Math.round(gain);
                el.classList.remove('show');
                void el.offsetWidth;
                el.classList.add('show');
              }
            }
          }
        }
      } else {
        lastGameRef.current = reached;
      }

      const done = f >= STEPS;
      for (const v of villages) {
        const tk = tokenRefs.current[v];
        if (tk) tk.classList.toggle('win', done && v === leader);
      }

      const cur = f === 0 ? 0 : Math.min(STEPS, Math.ceil(f - 1e-9));
      if (dayNRef.current) dayNRef.current.textContent = String(cur);
      if (dayLabelRef.current) {
        dayLabelRef.current.textContent =
          f === 0 ? 'prima della partenza' : gameNames[cur] || '';
      }
    };

    const frame = (ts: number) => {
      if (startTsRef.current === null) startTsRef.current = ts - elapsedRef.current;
      elapsedRef.current = ts - startTsRef.current;
      if (elapsedRef.current >= totalMs()) {
        elapsedRef.current = totalMs();
        rafRef.current = null;
        renderAt(STEPS, true);
        return;
      }
      renderAt(fOf(elapsedRef.current), true);
      rafRef.current = requestAnimationFrame(frame);
    };
    const stop = () => {
      if (rafRef.current !== null) { cancelAnimationFrame(rafRef.current); rafRef.current = null; }
    };
    const play = () => {
      stop();
      if (elapsedRef.current >= totalMs()) { elapsedRef.current = 0; lastGameRef.current = 0; }
      startTsRef.current = null;
      rafRef.current = requestAnimationFrame(frame);
    };
    const jump = (delta: number) => {
      stop();
      const g = Math.max(0, Math.min(STEPS, Math.round(fOf(elapsedRef.current)) + delta));
      elapsedRef.current = msOf(g);
      renderAt(g, false);
    };
    const replay = () => {
      stop(); elapsedRef.current = 0; lastGameRef.current = 0;
      renderAt(0, false); play();
    };

    apiRef.current = { jump, replay };
    elapsedRef.current = totalMs();           // land on the final result
    renderAt(STEPS, false);                   // static; Replay starts the animation

    return () => { stop(); };
  }, [data]);

  const cssVars = {
    '--mr-line': theme.palette.divider,
    '--mr-panel': alpha(theme.palette.text.primary, 0.06),
    '--mr-muted': theme.palette.text.secondary,
    '--mr-accent': theme.palette.success.main,
    '--mr-grid-min': alpha(theme.palette.text.primary, 0.05),
    '--mr-grid-maj': alpha(theme.palette.text.primary, 0.13),
  } as React.CSSProperties;

  return (
    <Container maxWidth="lg" sx={{ pt: 2, pb: 4 }}>
      <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', mb: 1 }}>
        <Typography variant="h4" component="h1">Classifica</Typography>
        <YearSelector />
      </Box>

      {loading && (
        <Box sx={{ display: 'flex', justifyContent: 'center', my: 6 }}>
          <CircularProgress />
        </Box>
      )}

      {!loading && error && (
        <Alert severity="error" sx={{ mt: 2 }}>
          Errore nel caricamento della classifica: {error}
        </Alert>
      )}

      {!loading && !error && data && (
        <>
          <Box sx={{ display: 'flex', alignItems: 'baseline', gap: 2, mb: 1, flexWrap: 'wrap' }}>
            <Typography variant="h5" component="div" sx={{ fontVariantNumeric: 'tabular-nums' }}>
              <span ref={dayNRef}>0</span>
              <Typography component="span" variant="body2" color="text.secondary">
                {' / ' + data.totalGames}
              </Typography>
            </Typography>
            <Typography
              variant="subtitle1" component="span" fontWeight={600}
              ref={dayLabelRef as React.Ref<HTMLSpanElement>}
              sx={{ minWidth: 0 }}
            >
              prima della partenza
            </Typography>
          </Box>

          <Card variant="outlined" sx={{ overflow: 'visible' }}>
            <CardContent sx={{ pt: 1.5, px: 2, pb: 2, '&:last-child': { pb: 2 } }}>
              <Box className="mascot-race" sx={cssVars}>
                <div className="podium pre" ref={podiumRef}>
                  {SLOT_PLACE.map((place, slot) => (
                    <div
                      key={'step' + slot}
                      className="step"
                      style={{
                        left: `calc(${slot} * 20% + 7px)`,
                        height: `calc(var(--podH) * ${HEIGHTS[place - 1]})`,
                      }}
                    >
                      <span className="place">{MEDALS[place - 1]}</span>
                    </div>
                  ))}
                  {data.villages.map((v) => {
                    const color = data.colors[v] || '#888888';
                    return (
                      <div
                        key={'ptok' + v}
                        className="ptok"
                        ref={(el) => { tokRefs.current[v] = el; }}
                      >
                        <span className="dot" style={{ background: color, color: textOn(color) }}>
                          {MASCOTS[v] || FALLBACK_EMOJI}
                        </span>
                        <span className="tp" ref={(el) => { tokPtsRefs.current[v] = el; }}>0</span>
                        {v === lovedBorgo && (
                          <RouterLink
                            to="/borgo-amato"
                            className="loved"
                            aria-label="Borgo più amato — vota"
                            title="Vota il tuo borgo preferito"
                          >
                            <i aria-hidden>❤</i>
                            <i aria-hidden>❤</i>
                            <i aria-hidden>❤</i>
                            <i aria-hidden>❤</i>
                            <i aria-hidden>❤</i>
                          </RouterLink>
                        )}
                      </div>
                    );
                  })}
                </div>

                <div className="board">
                  {data.villages.map((v) => {
                    const color = data.colors[v] || '#888888';
                    return (
                      <div className="lane" key={v}>
                        <div className="who">
                          <span className="swatch" style={{ background: color }} />
                          <span className="name">{v}</span>
                          <span className="crown" ref={(el) => { crownRefs.current[v] = el; }}>👑</span>
                        </div>
                        <div className="track">
                          <div className="rail">
                            <div
                              className="token"
                              ref={(el) => { tokenRefs.current[v] = el; }}
                              style={{ background: color, color: textOn(color) }}
                            >
                              {MASCOTS[v] || FALLBACK_EMOJI}
                            </div>
                          </div>
                        </div>
                        <div className="pts">
                          <span className="delta" ref={(el) => { deltaRefs.current[v] = el; }} />
                          <span ref={(el) => { ptsRefs.current[v] = el; }}>0</span>
                        </div>
                      </div>
                    );
                  })}
                </div>
              </Box>
            </CardContent>
          </Card>

          <Stack direction="row" spacing={1} alignItems="center" sx={{ mt: 2 }}>
            <IconButton size="small" aria-label="gioco precedente"
              onClick={() => apiRef.current?.jump(-1)}>
              <ChevronLeftIcon fontSize="small" />
            </IconButton>
            <IconButton size="small" aria-label="gioco successivo"
              onClick={() => apiRef.current?.jump(1)}>
              <ChevronRightIcon fontSize="small" />
            </IconButton>
            <Button size="small" variant="outlined" startIcon={<ReplayIcon />}
              onClick={() => apiRef.current?.replay()}>
              Replay
            </Button>
          </Stack>
        </>
      )}
    </Container>
  );
};

export default MascotRace;
