import React, {useState, useEffect, useRef, useCallback} from 'react';
import {Link as RouterLink} from 'react-router-dom';
import {
   Container,
   Typography,
   Box,
   Card,
   CardContent,
   CircularProgress,
   Alert,
   Button,
   Select,
   MenuItem,
   FormControl,
   InputLabel,
} from '@mui/material';
import {PalioData} from '../../../generated/types.gen';
import {getPalioDataForYear} from '../../../utils/yearApi';
import {submitMiniGameScore} from '../../../utils/minigameApi';
import {useYear} from '../../../contexts/YearContext';

// Flappy-Bird tuning, per-frame @60fps (proven reference values:
// gravity ~0.5, flap impulse ~-7.6). The loop normalises real dt into
// "frames elapsed" — same technique as Borgo Dino — so the feel is
// refresh-rate independent.
const FPS = 60;
const G = 0.45;
const FLAP_V = -7.4;
const MAX_FALL = 11;

const CW = 420;
const CH = 560;
const GROUND_H = 56;
const GROUND_Y = CH - GROUND_H;

const BIRD_X = 104;
const BIRD_R = 15;

const PIPE_W = 64;
const GAP = 160;
const PIPE_SPEED = 2.7;
const SPAWN_GAP_PX = 224;
const PIPE_COLOR = '#5a7d2a';

const HI_KEY = 'flappyBorgoHi';

interface Pipe {
   x: number;
   gapCenter: number;
   passed: boolean;
}

const randRange = (a: number, b: number) => a + Math.random() * (b - a);

const FlappyGamePage: React.FC = () => {
   const [palioData, setPalioData] = useState<PalioData | null>(null);
   const [loading, setLoading] = useState(true);
   const [error, setError] = useState<string | null>(null);
   const [selectedBorgo, setSelectedBorgo] = useState<string | null>(null);
   const [status, setStatus] = useState<'play' | 'gameover'>('play');
   const [runKey, setRunKey] = useState(0);
   const [hud, setHud] = useState({score: 0, hi: 0});
   const {selectedYear} = useYear();

   const canvasRef = useRef<HTMLCanvasElement>(null);
   const flapRef = useRef(false);

   useEffect(() => {
      const fetchData = async () => {
         try {
            setLoading(true);
            const response = await getPalioDataForYear(selectedYear);
            if (response.error) throw new Error('Failed to fetch palio data');
            setPalioData(response.data!);
         } catch (err) {
            setError(err instanceof Error ? err.message : 'An error occurred');
         } finally {
            setLoading(false);
         }
      };
      fetchData();
   }, [selectedYear]);

   useEffect(() => {
      const raw = Number(window.localStorage.getItem(HI_KEY) || 0);
      setHud((h) => ({...h, hi: Number.isFinite(raw) ? raw : 0}));
   }, []);

   const borgoColor: string = (selectedBorgo
      ? (palioData?.villages_colors as Record<string, string> | undefined)?.[selectedBorgo]
      : undefined) ?? '#f4c20d';

   const startWithBorgo = (borgo: string) => {
      setSelectedBorgo(borgo);
      setStatus('play');
      setRunKey((k) => k + 1);
   };

   const restart = useCallback(() => {
      setStatus('play');
      setRunKey((k) => k + 1);
   }, []);

   // Best run only — server takes max. Submit once per finished run.
   const submittedRun = useRef(-1);
   useEffect(() => {
      if (status === 'gameover' && selectedBorgo && submittedRun.current !== runKey) {
         submittedRun.current = runKey;
         submitMiniGameScore({game: 'flappy', borgo: selectedBorgo, score: hud.score});
      }
   }, [status, runKey, selectedBorgo, hud.score]);

   useEffect(() => {
      if (!selectedBorgo || status === 'gameover') return;
      const canvas = canvasRef.current;
      if (!canvas) return;
      const ctx = canvas.getContext('2d');
      if (!ctx) return;

      let y = CH * 0.42;
      let vy = 0;
      let started = false;
      let crashed = false;
      const pipes: Pipe[] = [];
      let nextSpawnX = CW + 80;
      let scoreVal = 0;
      let hi = hud.hi;
      let raf = 0;
      let last = performance.now();

      const spawn = () => {
         const minC = GAP / 2 + 46;
         const maxC = GROUND_Y - GAP / 2 - 46;
         pipes.push({x: CW + PIPE_W, gapCenter: randRange(minC, maxC), passed: false});
      };
      spawn();

      const endGame = () => {
         crashed = true;
         if (scoreVal > hi) {
            hi = scoreVal;
            try {
               window.localStorage.setItem(HI_KEY, String(hi));
            } catch {
               /* ignore quota / privacy mode */
            }
         }
         setHud({score: scoreVal, hi});
         setStatus('gameover');
      };

      const step = (now: number) => {
         const fe = Math.min(((now - last) / 1000) * FPS, 3); // frames elapsed
         last = now;

         const flap = flapRef.current;
         flapRef.current = false;

         if (!started) {
            if (flap) {
               started = true;
               vy = FLAP_V;
            }
         } else if (!crashed) {
            if (flap) vy = FLAP_V;
            vy = Math.min(vy + G * fe, MAX_FALL);
            y += vy * fe;

            if (y - BIRD_R < 0) {
               y = BIRD_R;
               if (vy < 0) vy = 0;
            }

            for (const p of pipes) p.x -= PIPE_SPEED * fe;
            nextSpawnX -= PIPE_SPEED * fe;
            if (nextSpawnX <= 0) {
               spawn();
               nextSpawnX = SPAWN_GAP_PX;
            }
            while (pipes.length && pipes[0].x + PIPE_W < -4) pipes.shift();

            // hitbox: a forgiving box around the bird
            const bx = BIRD_X - 12;
            const bw = 24;
            const bTop = y - 11;
            const bBot = y + 11;

            for (const p of pipes) {
               if (!p.passed && p.x + PIPE_W < BIRD_X) {
                  p.passed = true;
                  scoreVal += 1;
               }
               const gapTop = p.gapCenter - GAP / 2;
               const gapBot = p.gapCenter + GAP / 2;
               const inX = bx + bw > p.x && bx < p.x + PIPE_W;
               if (inX && (bTop < gapTop || bBot > gapBot)) endGame();
            }

            if (y + BIRD_R >= GROUND_Y) {
               y = GROUND_Y - BIRD_R;
               endGame();
            }

            setHud((h) => (h.score === scoreVal && h.hi === hi ? h : {score: scoreVal, hi}));
         }

         // ---------- draw ----------
         ctx.fillStyle = '#9ad7e8';
         ctx.fillRect(0, 0, CW, CH);

         for (const p of pipes) {
            const gapTop = p.gapCenter - GAP / 2;
            const gapBot = p.gapCenter + GAP / 2;
            ctx.fillStyle = PIPE_COLOR;
            ctx.fillRect(p.x, 0, PIPE_W, gapTop);
            ctx.fillRect(p.x, gapBot, PIPE_W, GROUND_Y - gapBot);
            ctx.fillStyle = '#46611f';
            ctx.fillRect(p.x - 4, gapTop - 18, PIPE_W + 8, 18);
            ctx.fillRect(p.x - 4, gapBot, PIPE_W + 8, 18);
         }

         // ground
         ctx.fillStyle = '#ded895';
         ctx.fillRect(0, GROUND_Y, CW, GROUND_H);
         ctx.fillStyle = '#c4bd6f';
         ctx.fillRect(0, GROUND_Y, CW, 6);

         drawBird(ctx, y, vy, borgoColor, crashed);

         // HUD
         ctx.fillStyle = '#2b2b2b';
         ctx.textBaseline = 'top';
         ctx.textAlign = 'left';
         ctx.font = 'bold 13px monospace';
         ctx.fillText(selectedBorgo!.toUpperCase(), 14, 12);
         ctx.textAlign = 'right';
         ctx.font = 'bold 14px monospace';
         ctx.fillText(`HI ${hi}`, CW - 14, 12);
         ctx.textAlign = 'center';
         ctx.font = 'bold 40px monospace';
         ctx.fillText(String(scoreVal), CW / 2, 40);

         if (!started) {
            ctx.fillStyle = '#2b2b2b';
            ctx.font = 'bold 16px monospace';
            ctx.textAlign = 'center';
            ctx.fillText('Tocca / Spazio per volare', CW / 2, CH / 2 + 40);
         }

         raf = requestAnimationFrame(step);
      };

      raf = requestAnimationFrame(step);
      return () => cancelAnimationFrame(raf);
      // eslint-disable-next-line react-hooks/exhaustive-deps
   }, [selectedBorgo, borgoColor, runKey, status]);

   useEffect(() => {
      const onKey = (e: KeyboardEvent) => {
         if (e.key === ' ' || e.key === 'ArrowUp' || e.key === 'w') {
            e.preventDefault();
            flapRef.current = true;
         }
      };
      window.addEventListener('keydown', onKey);
      return () => window.removeEventListener('keydown', onKey);
   }, []);

   if (loading) {
      return (
         <Container maxWidth="lg">
            <Box sx={{mt: 4, mb: 4, display: 'flex', justifyContent: 'center'}}>
               <CircularProgress/>
            </Box>
         </Container>
      );
   }
   if (error) {
      return (
         <Container maxWidth="lg">
            <Box sx={{mt: 4, mb: 4}}>
               <Alert severity="error">Errore nel caricamento dei dati: {error}</Alert>
            </Box>
         </Container>
      );
   }

   const villages = palioData?.villages ?? [];
   const noSelect = {
      userSelect: 'none',
      WebkitUserSelect: 'none',
      WebkitTouchCallout: 'none',
      WebkitTapHighlightColor: 'transparent',
      touchAction: 'none',
   } as const;

   return (
      <Container maxWidth="lg">
         <Box sx={{mt: 4, mb: 4}}>
            <Box sx={{mb: 3}}>
               <Button component={RouterLink} to=".." size="small" sx={{minWidth: 0, pl: 0, mb: 0.5}}>
                  ← Mini-giochi
               </Button>
               <Typography variant="h4" component="h1">
                  Flappy Borgo
               </Typography>
            </Box>

            {!selectedBorgo ? (
               <Card>
                  <CardContent>
                     <Typography variant="h6" gutterBottom>
                        Scegli il tuo borgo
                     </Typography>
                     <FormControl sx={{minWidth: 260, mt: 1}}>
                        <InputLabel id="borgo-select-label">Borgo</InputLabel>
                        <Select
                           labelId="borgo-select-label"
                           label="Borgo"
                           value=""
                           onChange={(e) => startWithBorgo(e.target.value as string)}
                        >
                           {villages.map((v) => (
                              <MenuItem key={v} value={v}>
                                 {v}
                              </MenuItem>
                           ))}
                        </Select>
                     </FormControl>
                     {villages.length === 0 && (
                        <Typography variant="body2" color="text.secondary" sx={{mt: 2}}>
                           Nessun borgo disponibile per questo anno.
                        </Typography>
                     )}
                  </CardContent>
               </Card>
            ) : (
               <Card>
                  <CardContent>
                     <Box
                        sx={{
                           ...noSelect,
                           display: 'flex',
                           justifyContent: 'space-between',
                           alignItems: 'center',
                           mb: 2,
                           flexWrap: 'wrap',
                           gap: 1,
                        }}
                     >
                        <Box sx={{display: 'flex', flexDirection: 'column'}}>
                           <Typography variant="h6">{selectedBorgo}</Typography>
                           <Typography variant="body2" color="text.secondary">
                              🏆 record {hud.hi} · punti {hud.score}
                           </Typography>
                        </Box>
                        <Box sx={{display: 'flex', gap: 1}}>
                           <Button variant="outlined" size="small" onClick={restart}>
                              Ricomincia
                           </Button>
                           <Button variant="text" size="small" onClick={() => setSelectedBorgo(null)}>
                              Cambia borgo
                           </Button>
                        </Box>
                     </Box>

                     <Box
                        onPointerDown={(e) => {
                           e.preventDefault();
                           if (status !== 'gameover') flapRef.current = true;
                        }}
                        onContextMenu={(e) => e.preventDefault()}
                        sx={{
                           ...noSelect,
                           position: 'relative',
                           width: '100%',
                           display: 'flex',
                           justifyContent: 'center',
                           cursor: 'pointer',
                        }}
                     >
                        <canvas
                           ref={canvasRef}
                           width={CW}
                           height={CH}
                           draggable={false}
                           style={{
                              width: '100%',
                              maxWidth: CW,
                              height: 'auto',
                              borderRadius: 8,
                              display: 'block',
                              touchAction: 'none',
                              userSelect: 'none',
                              WebkitUserSelect: 'none',
                           }}
                        />
                        {status === 'gameover' && (
                           <Box
                              sx={{
                                 ...noSelect,
                                 position: 'absolute',
                                 inset: 0,
                                 display: 'flex',
                                 flexDirection: 'column',
                                 alignItems: 'center',
                                 justifyContent: 'center',
                                 bgcolor: 'rgba(0,0,0,0.6)',
                                 color: '#fff',
                                 borderRadius: 2,
                                 gap: 1.5,
                              }}
                           >
                              <Typography variant="h4">G A M E   O V E R</Typography>
                              <Typography variant="body1">
                                 Punti {hud.score} · Record {hud.hi}
                              </Typography>
                              <Button variant="contained" onClick={restart}>
                                 Riprova
                              </Button>
                           </Box>
                        )}
                     </Box>

                     <Box sx={{...noSelect, mt: 2, display: 'flex', justifyContent: 'center'}}>
                        <Box
                           onPointerDown={(e) => {
                              e.preventDefault();
                              if (status !== 'gameover') flapRef.current = true;
                           }}
                           sx={{
                              ...noSelect,
                              width: '100%',
                              maxWidth: 320,
                              height: {xs: 56, sm: 62},
                              display: 'flex',
                              alignItems: 'center',
                              justifyContent: 'center',
                              borderRadius: 2,
                              bgcolor: borgoColor,
                              color: '#fff',
                              fontSize: {xs: 16, sm: 18},
                              fontWeight: 700,
                              cursor: 'pointer',
                              boxShadow: 2,
                              '&:active': {filter: 'brightness(0.85)'},
                           }}
                        >
                           VOLA
                        </Box>
                     </Box>
                  </CardContent>
               </Card>
            )}
         </Box>
      </Container>
   );
};

function drawBird(
   ctx: CanvasRenderingContext2D,
   y: number,
   vy: number,
   color: string,
   dead: boolean,
) {
   const x = BIRD_X;
   ctx.save();
   ctx.translate(x, y);
   const tilt = Math.max(-0.5, Math.min(0.9, vy / 12));
   ctx.rotate(tilt);
   // body
   ctx.fillStyle = color;
   ctx.beginPath();
   ctx.arc(0, 0, BIRD_R, 0, Math.PI * 2);
   ctx.fill();
   // wing
   ctx.fillStyle = 'rgba(255,255,255,0.55)';
   ctx.fillRect(-10, 1, 12, 6);
   // beak
   ctx.fillStyle = '#e8662a';
   ctx.fillRect(BIRD_R - 3, -3, 9, 6);
   // eye
   ctx.fillStyle = '#fff';
   ctx.beginPath();
   ctx.arc(6, -5, 4, 0, Math.PI * 2);
   ctx.fill();
   ctx.fillStyle = '#222';
   ctx.beginPath();
   ctx.arc(dead ? 5 : 7, -5, 2, 0, Math.PI * 2);
   ctx.fill();
   ctx.restore();
}

export default FlappyGamePage;
