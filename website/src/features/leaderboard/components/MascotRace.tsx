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
import { hexToRgb } from '../../../utils/colorUtils';
import YearSelector from '../../../components/YearSelector';
import './MascotRace.css';

/* Animated leaderboard replay. MUI shell + a custom race field/podium
   themed from the MUI theme. The 60fps engine is imperative (refs + rAF)
   so there are no per-frame re-renders. Data is real: cumulative
   per-game points are reconstructed from game_leaderboards (division
   games averaged), then each series is anchored so its final frame
   equals the official palio_leaderboard total exactly. */

// The API has no mascots — map the festival's 5 borghi by name.
const MASCOTS: Record<string, string> = {
  Sornico: '🐿️', Sottocastello: '🐎', Salt: '🦐', Sottomonte: '🐰', Villa: '🐼',
};
const FALLBACK_EMOJI = '🏁';

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
  series: Record<string, number[]>;   // cumulative points, index 0..steps
  gameNames: string[];                // index 0 = "Partenza"
  steps: number;
}

// Reconstruct cumulative per-game points, then anchor each village's final
// value to its official palio_leaderboard total.
function buildRaceData(lb: Leaderboard, palio: PalioData): RaceData {
  const villages = (palio.villages?.length ? palio.villages : lb.villages).slice();
  const colors = palio.villages_colors || {};
  const order = Object.keys(lb.game_leaderboards).sort();   // G01, G02, …

  const cum: Record<string, number> = {};
  const series: Record<string, number[]> = {};
  villages.forEach((v) => { cum[v] = 0; series[v] = [0]; });

  for (const gid of order) {
    const e = lb.game_leaderboards[gid];
    const gp: Record<string, number> = {};
    villages.forEach((v) => { gp[v] = 0; });

    if (e.divisions && e.divisions.length) {
      const n = e.divisions.length;
      for (const d of e.divisions) {
        for (const [v, info] of Object.entries(d.leaderboard || {})) {
          if (v in gp) gp[v] += (info.points || 0) / n;
        }
      }
    }
    for (const [v, info] of Object.entries(e.overall_leaderboard || {})) {
      if (v in gp) gp[v] += info.points || 0;
    }
    villages.forEach((v) => { cum[v] += gp[v]; series[v].push(cum[v]); });
  }

  for (const v of villages) {
    const official = lb.palio_leaderboard[v]?.points ?? 0;
    const last = series[v][series[v].length - 1];
    const k = last > 0 ? official / last : 0;
    series[v] = series[v].map((x) => x * k);
    series[v][series[v].length - 1] = official;          // exact final
  }

  const gameNames = ['Partenza', ...order.map((g) => lb.game_leaderboards[g].game_name || g)];
  return { villages, colors, series, gameNames, steps: order.length };
}

const MascotRace: React.FC = () => {
  const theme = useTheme();
  const { selectedYear } = useYear();

  const [data, setData] = useState<RaceData | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

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
    const MAXPTS = STEPS * 10 + 10;          // rule ceiling, fixed scale
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
                {' / ' + data.steps}
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

          <Card variant="outlined">
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
