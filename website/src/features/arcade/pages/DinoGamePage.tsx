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
import {useYear} from '../../../contexts/YearContext';

// ---- Constants taken verbatim from the Chromium t-rex-runner source
// (per-frame @60fps). The loop normalises real dt into "frames elapsed"
// so the original tuning is preserved on any refresh rate.
const FPS = 60;
const T_GRAVITY = 0.6;
const T_INITIAL_JUMP_V = -10;
const T_DROP_V = -5;
const T_SPEED_DROP_COEFF = 3;
const T_MIN_JUMP_HEIGHT = 30;
const TREX_W = 44;
const TREX_H = 47;
const TREX_H_DUCK = 26;
const TREX_W_DUCK = 59;
const TREX_X = 40;

const START_SPEED = 6;
const MAX_SPEED = 13;
const ACCELERATION = 0.001;
const GAP_COEFFICIENT = 0.6;
const SCORE_COEFF = 0.025;
const INVERT_DISTANCE = 700; // score units between day/night flips
const PTERO_MIN_SPEED = 8.5;

const CW = 600;
const CH = 240;
const GROUND_Y = CH - 16; // top of the ground line
const TREX_GROUND = GROUND_Y - TREX_H;

const CACTUS_SMALL = {w: 17, h: 35};
const CACTUS_LARGE = {w: 25, h: 50};
const PTERO = {w: 46, h: 40};
const PTERO_HEIGHTS = [GROUND_Y - 78, GROUND_Y - 52, GROUND_Y - 34];

const HI_KEY = 'borgoDinoHi';

interface Obstacle {
   x: number;
   w: number;
   h: number;
   y: number;
   type: 'cactus' | 'ptero';
   size: number;
   frame: number;
}

const randInt = (a: number, b: number) => Math.floor(a + Math.random() * (b - a + 1));

const DinoGamePage: React.FC = () => {
   const [palioData, setPalioData] = useState<PalioData | null>(null);
   const [loading, setLoading] = useState(true);
   const [error, setError] = useState<string | null>(null);
   const [selectedBorgo, setSelectedBorgo] = useState<string | null>(null);
   const [status, setStatus] = useState<'play' | 'gameover'>('play');
   const [runKey, setRunKey] = useState(0);
   const [hud, setHud] = useState({score: 0, hi: 0});
   const {selectedYear} = useYear();

   const canvasRef = useRef<HTMLCanvasElement>(null);
   const keys = useRef<Record<string, boolean>>({});

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
      : undefined) ?? '#535353';

   const startWithBorgo = (borgo: string) => {
      setSelectedBorgo(borgo);
      setStatus('play');
      setRunKey((k) => k + 1);
   };

   const restart = useCallback(() => {
      setStatus('play');
      setRunKey((k) => k + 1);
   }, []);

   useEffect(() => {
      if (!selectedBorgo || status === 'gameover') return;
      const canvas = canvasRef.current;
      if (!canvas) return;
      const ctx = canvas.getContext('2d');
      if (!ctx) return;

      const t = {
         y: TREX_GROUND, vy: 0, jumping: false, ducking: false,
         speedDrop: false, reachedMin: false, run: 0,
      };
      const obstacles: Obstacle[] = [];
      const clouds: {x: number; y: number}[] = [];
      let speed = START_SPEED;
      let distance = 0;
      let started = false;
      let crashed = false;
      let nextSpawn = CW + 60;
      let invert = false;
      let lastInvertScore = 0;
      let hi = hud.hi;
      let prevJump = false;
      let raf = 0;
      let last = performance.now();

      const score = () => Math.floor(distance * SCORE_COEFF);

      const trexBox = () =>
         t.ducking
            ? {
                 // ducking: short box anchored to the ground so high
                 // pterodactyls pass over (matches the drawn sprite)
                 x: TREX_X + 4,
                 y: GROUND_Y - TREX_H_DUCK + 3,
                 w: TREX_W_DUCK - 16,
                 h: TREX_H_DUCK - 5,
              }
            : {
                 x: TREX_X + 5,
                 y: t.y + 4,
                 w: TREX_W - 12,
                 h: TREX_H - 6,
              };

      const spawn = () => {
         const canPtero = speed > PTERO_MIN_SPEED && Math.random() < 0.3;
         if (canPtero) {
            obstacles.push({
               x: CW + 10, w: PTERO.w, h: PTERO.h,
               y: PTERO_HEIGHTS[randInt(0, 2)], type: 'ptero',
               size: 1, frame: 0,
            });
         } else {
            const large = Math.random() < 0.45;
            const base = large ? CACTUS_LARGE : CACTUS_SMALL;
            const size = large ? 1 : randInt(1, 3);
            obstacles.push({
               x: CW + 10, w: base.w * size, h: base.h,
               y: GROUND_Y - base.h, type: 'cactus',
               size, frame: 0,
            });
         }
         const lead = obstacles[obstacles.length - 1];
         const minGap = Math.round(lead.w * speed + 120 * GAP_COEFFICIENT);
         const gap = randInt(minGap, Math.round(minGap * 1.5));
         nextSpawn = CW + gap;
      };

      const collide = (o: Obstacle) => {
         const b = trexBox();
         const ox = o.x + 3;
         const ow = o.w - 6;
         return b.x < ox + ow && b.x + b.w > ox && b.y < o.y + o.h && b.y + b.h > o.y;
      };

      const endGame = () => {
         crashed = true;
         if (score() > hi) {
            hi = score();
            try {
               window.localStorage.setItem(HI_KEY, String(hi));
            } catch {
               /* ignore quota / privacy mode */
            }
         }
         setHud({score: score(), hi});
         setStatus('gameover');
      };

      const step = (now: number) => {
         const fe = Math.min(((now - last) / 1000) * FPS, 3); // frames elapsed
         last = now;

         const jumpHeld = keys.current['ArrowUp'] || keys.current[' '] || keys.current['w'];
         const downHeld = keys.current['ArrowDown'] || keys.current['s'];
         const jumpPressed = jumpHeld && !prevJump;
         prevJump = jumpHeld;

         if (!started) {
            if (jumpPressed) started = true;
         } else if (!crashed) {
            distance += speed * fe;
            if (speed < MAX_SPEED) speed += ACCELERATION * fe;

            // jump start
            if (jumpPressed && !t.jumping && !t.ducking) {
               t.jumping = true;
               t.vy = T_INITIAL_JUMP_V;
               t.reachedMin = false;
               t.speedDrop = false;
            }
            // early release -> cut the jump (authentic variable height)
            if (!jumpHeld && t.jumping && t.reachedMin && t.vy < T_DROP_V) {
               t.vy = T_DROP_V;
            }
            // duck
            if (t.jumping) {
               t.ducking = false;
               if (downHeld) t.speedDrop = true;
            } else {
               t.ducking = downHeld;
            }

            if (t.jumping) {
               const g = t.speedDrop ? T_GRAVITY * T_SPEED_DROP_COEFF : T_GRAVITY;
               t.y += t.vy * fe;
               t.vy += g * fe;
               if (TREX_GROUND - t.y > T_MIN_JUMP_HEIGHT) t.reachedMin = true;
               if (t.y >= TREX_GROUND) {
                  t.y = TREX_GROUND;
                  t.jumping = false;
                  t.vy = 0;
                  t.speedDrop = false;
               }
            }

            // obstacles
            nextSpawn -= speed * fe;
            if (nextSpawn <= 0) spawn();
            for (const o of obstacles) {
               o.x -= speed * fe;
               if (o.type === 'ptero') o.frame = Math.floor(now / 150) % 2;
               if (collide(o)) endGame();
            }
            while (obstacles.length && obstacles[0].x + obstacles[0].w < -10) obstacles.shift();

            // clouds
            if (clouds.length < 5 && Math.random() < 0.01) {
               clouds.push({x: CW + 20, y: 20 + Math.random() * 50});
            }
            for (const c of clouds) c.x -= speed * 0.35 * fe;
            while (clouds.length && clouds[0].x < -60) clouds.shift();

            // day / night invert
            if (score() - lastInvertScore >= INVERT_DISTANCE) {
               lastInvertScore = score();
               invert = !invert;
            }

            // run animation
            t.run += speed * fe * 0.06;

            setHud((h) => (h.score === score() && h.hi === hi ? h : {score: score(), hi}));
         }

         // ---------- draw ----------
         const bg = invert ? '#1b1b1b' : '#f7f7f7';
         const fg = invert ? '#f7f7f7' : '#535353';
         const dino = invert ? '#f7f7f7' : borgoColor;
         ctx.fillStyle = bg;
         ctx.fillRect(0, 0, CW, CH);

         for (const c of clouds) drawCloud(ctx, c.x, c.y, fg);

         // ground
         ctx.strokeStyle = fg;
         ctx.lineWidth = 2;
         ctx.beginPath();
         ctx.moveTo(0, GROUND_Y + 1);
         ctx.lineTo(CW, GROUND_Y + 1);
         ctx.stroke();
         ctx.fillStyle = fg;
         for (let i = 0; i < CW / 33 + 1; i++) {
            const gx = ((i * 33 - (distance % 33)) % (CW + 33) + CW + 33) % (CW + 33);
            ctx.fillRect(gx, GROUND_Y + 5, i % 2 ? 10 : 4, 2);
         }

         for (const o of obstacles) {
            if (o.type === 'cactus') drawCactus(ctx, o, fg);
            else drawPtero(ctx, o, fg);
         }

         drawTrex(ctx, t.y, t.ducking, t.jumping, Math.floor(t.run) % 2 === 0, crashed, dino);

         // HUD — borgo name and score on separate lines
         ctx.fillStyle = fg;
         ctx.textBaseline = 'top';
         ctx.textAlign = 'left';
         ctx.font = 'bold 13px monospace';
         ctx.fillText(selectedBorgo!.toUpperCase(), 14, 10);
         ctx.textAlign = 'right';
         ctx.font = 'bold 18px monospace';
         ctx.fillText(
            `HI ${String(hi).padStart(5, '0')}  ${String(score()).padStart(5, '0')}`,
            CW - 14, 30,
         );

         if (!started) {
            ctx.fillStyle = fg;
            ctx.font = 'bold 17px monospace';
            ctx.textAlign = 'center';
            ctx.fillText('Premi Spazio / ↑ o tocca SALTA per iniziare', CW / 2, CH / 2 - 6);
         }

         raf = requestAnimationFrame(step);
      };

      raf = requestAnimationFrame(step);
      return () => cancelAnimationFrame(raf);
      // eslint-disable-next-line react-hooks/exhaustive-deps
   }, [selectedBorgo, borgoColor, runKey, status]);

   useEffect(() => {
      const blocked = ['ArrowUp', 'ArrowDown', ' '];
      const down = (e: KeyboardEvent) => {
         if (blocked.includes(e.key)) e.preventDefault();
         keys.current[e.key] = true;
      };
      const up = (e: KeyboardEvent) => {
         keys.current[e.key] = false;
      };
      window.addEventListener('keydown', down);
      window.addEventListener('keyup', up);
      return () => {
         window.removeEventListener('keydown', down);
         window.removeEventListener('keyup', up);
      };
   }, []);

   const hold = (key: string) => ({
      onPointerDown: (e: React.PointerEvent) => {
         e.preventDefault();
         keys.current[key] = true;
      },
      onPointerUp: (e: React.PointerEvent) => {
         e.preventDefault();
         keys.current[key] = false;
      },
      onPointerLeave: () => {
         keys.current[key] = false;
      },
      onPointerCancel: () => {
         keys.current[key] = false;
      },
      onContextMenu: (e: React.MouseEvent) => e.preventDefault(),
   });

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
      msUserSelect: 'none',
      WebkitTouchCallout: 'none',
      WebkitTapHighlightColor: 'transparent',
      touchAction: 'none',
   } as const;

   const padSx = {
      ...noSelect,
      flex: 1,
      maxWidth: 220,
      height: {xs: 52, sm: 60},
      display: 'flex',
      alignItems: 'center',
      justifyContent: 'center',
      borderRadius: 2,
      bgcolor: borgoColor,
      color: '#fff',
      fontSize: {xs: 15, sm: 18},
      fontWeight: 700,
      cursor: 'pointer',
      boxShadow: 2,
      '&:active': {filter: 'brightness(0.85)'},
   };

   return (
      <Container maxWidth="lg">
         <Box sx={{mt: 4, mb: 4}}>
            <Box sx={{mb: 3}}>
               <Button component={RouterLink} to=".." size="small" sx={{minWidth: 0, pl: 0, mb: 0.5}}>
                  ← Mini-giochi
               </Button>
               <Typography variant="h4" component="h1">
                  Borgo Dino
               </Typography>
            </Box>

            {!selectedBorgo ? (
               <Card>
                  <CardContent>
                     <Typography variant="h6" gutterBottom>
                        Scegli il tuo borgo
                     </Typography>
                     <Typography variant="body2" color="text.secondary" sx={{mb: 3}}>
                        Endless runner alla Chrome Dino. Salta i cactus, abbassati sotto i
                        pterodattili, la velocità cresce all'infinito. Spazio / ↑ salta,
                        ↓ abbassati.
                     </Typography>
                     <FormControl sx={{minWidth: 260}}>
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
                        <Box sx={{...noSelect, display: 'flex', flexDirection: 'column'}}>
                           <Typography variant="h6" sx={noSelect}>
                              {selectedBorgo}
                           </Typography>
                           <Typography variant="body2" color="text.secondary" sx={noSelect}>
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
                        onContextMenu={(e) => e.preventDefault()}
                        sx={{
                           ...noSelect,
                           position: 'relative',
                           width: '100%',
                           display: 'flex',
                           justifyContent: 'center',
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
                              <Typography variant="h4" sx={noSelect}>
                                 G A M E   O V E R
                              </Typography>
                              <Typography variant="body1" sx={noSelect}>
                                 Punti {hud.score} · Record {hud.hi}
                              </Typography>
                              <Button variant="contained" onClick={restart}>
                                 Riprova
                              </Button>
                           </Box>
                        )}
                     </Box>

                     <Box
                        sx={{
                           ...noSelect,
                           mt: 2,
                           display: 'flex',
                           justifyContent: 'center',
                           gap: 2,
                        }}
                     >
                        <Box sx={padSx} {...hold('ArrowDown')}>
                           GIÙ
                        </Box>
                        <Box sx={padSx} {...hold(' ')}>
                           SALTA
                        </Box>
                     </Box>
                  </CardContent>
               </Card>
            )}
         </Box>
      </Container>
   );
};

// ---------------- drawing ----------------

function drawTrex(
   ctx: CanvasRenderingContext2D,
   y: number, ducking: boolean, jumping: boolean, stepA: boolean, dead: boolean, color: string,
) {
   ctx.fillStyle = color;
   if (ducking) {
      const dy = GROUND_Y - TREX_H_DUCK;
      ctx.fillRect(TREX_X, dy, TREX_W_DUCK - 14, TREX_H_DUCK);
      ctx.fillRect(TREX_X + TREX_W_DUCK - 22, dy - 4, 22, 16); // head low
      ctx.fillStyle = '#fff';
      ctx.fillRect(TREX_X + TREX_W_DUCK - 10, dy - 1, 3, 3);
      return;
   }
   const x = TREX_X;
   // tail + body
   ctx.fillRect(x, y + 14, 18, 14);
   ctx.fillRect(x + 12, y + 10, 20, 22);
   // head
   ctx.fillRect(x + 24, y, 20, 18);
   ctx.fillRect(x + 40, y + 6, 6, 6); // snout
   // eye
   ctx.fillStyle = '#fff';
   ctx.fillRect(x + 36, y + 4, 4, 4);
   if (dead) {
      ctx.fillRect(x + 36, y + 4, 4, 1);
      ctx.fillStyle = color;
      ctx.fillRect(x + 35, y + 3, 1, 6);
   }
   ctx.fillStyle = color;
   // arm
   ctx.fillRect(x + 28, y + 24, 8, 4);
   // legs (animate unless airborne)
   if (jumping) {
      ctx.fillRect(x + 14, y + 32, 7, 8);
      ctx.fillRect(x + 24, y + 32, 7, 8);
   } else if (stepA) {
      ctx.fillRect(x + 14, y + 32, 7, 12);
      ctx.fillRect(x + 24, y + 32, 7, 7);
   } else {
      ctx.fillRect(x + 14, y + 32, 7, 7);
      ctx.fillRect(x + 24, y + 32, 7, 12);
   }
}

function drawCactus(ctx: CanvasRenderingContext2D, o: Obstacle, color: string) {
   ctx.fillStyle = color;
   const unit = o.w / o.size;
   for (let i = 0; i < o.size; i++) {
      const cx = o.x + i * unit + unit / 2 - 4;
      ctx.fillRect(cx, o.y, 8, o.h);
      ctx.fillRect(cx - 6, o.y + o.h * 0.35, 6, 3);
      ctx.fillRect(cx - 6, o.y + o.h * 0.35, 3, o.h * 0.3);
      ctx.fillRect(cx + 8, o.y + o.h * 0.22, 6, 3);
      ctx.fillRect(cx + 11, o.y + o.h * 0.22, 3, o.h * 0.34);
   }
}

function drawPtero(ctx: CanvasRenderingContext2D, o: Obstacle, color: string) {
   ctx.fillStyle = color;
   const {x, y} = o;
   ctx.fillRect(x + 10, y + 14, 28, 8); // body
   ctx.fillRect(x + 34, y + 10, 12, 8); // head
   ctx.fillRect(x + 44, y + 13, 6, 4); // beak
   if (o.frame === 0) {
      ctx.fillRect(x, y + 2, 22, 8); // wings up
   } else {
      ctx.fillRect(x, y + 22, 22, 8); // wings down
   }
}

function drawCloud(ctx: CanvasRenderingContext2D, x: number, y: number, color: string) {
   ctx.fillStyle = color;
   ctx.globalAlpha = 0.35;
   ctx.fillRect(x, y, 38, 8);
   ctx.fillRect(x + 6, y - 5, 24, 8);
   ctx.fillRect(x + 12, y + 6, 28, 6);
   ctx.globalAlpha = 1;
}

export default DinoGamePage;
