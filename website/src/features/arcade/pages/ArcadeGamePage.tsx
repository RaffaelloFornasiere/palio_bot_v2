import React, {useState, useEffect, useRef, useCallback} from 'react';
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
   Stack,
} from '@mui/material';
import {PalioData} from '../../../generated/types.gen';
import {getPalioDataForYear} from '../../../utils/yearApi';
import {useYear} from '../../../contexts/YearContext';
import YearSelector from '../../../components/YearSelector';

// Distinct emoji per borgo, assigned by index so each borgo is always the same.
const BORGO_EMOJIS = ['🦅', '🐢', '🐗', '🐺', '🦊', '🦁', '🐉', '🦄', '🐌', '🐬', '🐏', '🦔', '🐈', '🦒', '🐘', '🦏', '🐎'];

const GAME_WIDTH = 800;
const GAME_HEIGHT = 400;
const GROUND_HEIGHT = 40;
const GROUND_TOP = GAME_HEIGHT - GROUND_HEIGHT;

const PLAYER_W = 30;
const PLAYER_H = 40;

const GRAVITY = 1800; // px/s^2
const MOVE_SPEED = 260; // px/s
const JUMP_VELOCITY = -680; // px/s

const COIN_RADIUS = 10;
const MAX_COINS = 6;
const COIN_SPAWN_MS = 1100;

interface Rect {
   x: number;
   y: number;
   w: number;
   h: number;
}

interface Coin {
   x: number;
   y: number;
}

// Static one-way platforms (you can jump up through them, land on top).
const PLATFORMS: Rect[] = [
   {x: 160, y: 290, w: 150, h: 22},
   {x: 400, y: 225, w: 150, h: 22},
   {x: 600, y: 300, w: 130, h: 22},
];

// Static background decoration (classic Mario-style scenery).
const CLOUDS = [
   {x: 90, y: 55, s: 1},
   {x: 340, y: 40, s: 1.3},
   {x: 560, y: 75, s: 0.9},
   {x: 710, y: 50, s: 1.1},
];
const HILLS = [
   {x: 120, r: 95},
   {x: 520, r: 125},
   {x: 770, r: 80},
];
const BUSHES = [
   {x: 250, s: 1},
   {x: 470, s: 1.3},
   {x: 660, s: 0.9},
];

const ArcadeGamePage: React.FC = () => {
   const [palioData, setPalioData] = useState<PalioData | null>(null);
   const [loading, setLoading] = useState(true);
   const [error, setError] = useState<string | null>(null);
   const [selectedBorgo, setSelectedBorgo] = useState<string | null>(null);
   const [score, setScore] = useState(0);
   const {selectedYear} = useYear();

   const canvasRef = useRef<HTMLCanvasElement>(null);
   const keysRef = useRef<Record<string, boolean>>({});
   const playerRef = useRef({x: 80, y: GROUND_TOP - PLAYER_H, vx: 0, vy: 0, onGround: true, facing: 1});
   const coinsRef = useRef<Coin[]>([]);
   const scoreRef = useRef(0);

   useEffect(() => {
      const fetchData = async () => {
         try {
            setLoading(true);
            const response = await getPalioDataForYear(selectedYear);
            if (response.error) {
               throw new Error('Failed to fetch palio data');
            }
            setPalioData(response.data!);
         } catch (err) {
            setError(err instanceof Error ? err.message : 'An error occurred');
         } finally {
            setLoading(false);
         }
      };
      fetchData();
   }, [selectedYear]);

   const borgoColor = selectedBorgo
      ? palioData?.villages_colors?.[selectedBorgo] ?? '#1976d2'
      : '#1976d2';
   const borgoEmoji = selectedBorgo && palioData?.villages
      ? BORGO_EMOJIS[palioData.villages.indexOf(selectedBorgo) % BORGO_EMOJIS.length]
      : '🏃';

   const resetGame = useCallback(() => {
      playerRef.current = {x: 80, y: GROUND_TOP - PLAYER_H, vx: 0, vy: 0, onGround: true, facing: 1};
      coinsRef.current = [];
      scoreRef.current = 0;
      setScore(0);
   }, []);

   const startWithBorgo = (borgo: string) => {
      setSelectedBorgo(borgo);
      resetGame();
   };

   // Game loop runs only while a borgo is selected.
   useEffect(() => {
      if (!selectedBorgo) return;

      const canvas = canvasRef.current;
      if (!canvas) return;
      const ctx = canvas.getContext('2d');
      if (!ctx) return;

      let raf = 0;
      let lastTime = performance.now();
      let coinTimer = 0;

      const spawnCoin = () => {
         if (coinsRef.current.length >= MAX_COINS) return;
         // Spawn either over the ground or hovering near a platform so it is reachable.
         const surfaces = [{x: 0, y: GROUND_TOP, w: GAME_WIDTH, h: 0}, ...PLATFORMS];
         const s = surfaces[Math.floor(Math.random() * surfaces.length)];
         const x = s.x + 20 + Math.random() * Math.max(20, s.w - 40);
         const y = s.y - 30 - Math.random() * 60;
         coinsRef.current.push({x, y});
      };

      const step = (now: number) => {
         const dt = Math.min((now - lastTime) / 1000, 0.05);
         lastTime = now;

         const keys = keysRef.current;
         const p = playerRef.current;

         // Horizontal movement
         const left = keys['ArrowLeft'] || keys['a'] || keys['A'];
         const right = keys['ArrowRight'] || keys['d'] || keys['D'];
         p.vx = (right ? MOVE_SPEED : 0) - (left ? MOVE_SPEED : 0);
         p.x = Math.max(0, Math.min(GAME_WIDTH - PLAYER_W, p.x + p.vx * dt));
         if (p.vx > 0) p.facing = 1;
         else if (p.vx < 0) p.facing = -1;

         // Jump
         const jump = keys['ArrowUp'] || keys['w'] || keys['W'] || keys[' '];
         if (jump && p.onGround) {
            p.vy = JUMP_VELOCITY;
            p.onGround = false;
         }

         // Vertical movement + one-way collision with ground and platforms
         p.vy += GRAVITY * dt;
         const prevBottom = p.y + PLAYER_H;
         let newY = p.y + p.vy * dt;
         const newBottom = newY + PLAYER_H;
         p.onGround = false;

         const solids: Rect[] = [{x: 0, y: GROUND_TOP, w: GAME_WIDTH, h: GROUND_HEIGHT}, ...PLATFORMS];
         for (const s of solids) {
            const horizontallyOver = p.x + PLAYER_W > s.x && p.x < s.x + s.w;
            if (
               p.vy >= 0 &&
               horizontallyOver &&
               prevBottom <= s.y + 1 &&
               newBottom >= s.y
            ) {
               newY = s.y - PLAYER_H;
               p.vy = 0;
               p.onGround = true;
            }
         }
         p.y = newY;

         // Coin spawning
         coinTimer += dt * 1000;
         if (coinTimer >= COIN_SPAWN_MS) {
            coinTimer = 0;
            spawnCoin();
         }

         // Coin collection (circle vs player rect)
         coinsRef.current = coinsRef.current.filter((c) => {
            const closestX = Math.max(p.x, Math.min(c.x, p.x + PLAYER_W));
            const closestY = Math.max(p.y, Math.min(c.y, p.y + PLAYER_H));
            const dx = c.x - closestX;
            const dy = c.y - closestY;
            const hit = dx * dx + dy * dy < COIN_RADIUS * COIN_RADIUS;
            if (hit) {
               scoreRef.current += 1;
               setScore(scoreRef.current);
            }
            return !hit;
         });

         // ---- Draw ----
         // Sky (classic Super Mario light blue)
         ctx.fillStyle = '#5c94fc';
         ctx.fillRect(0, 0, GAME_WIDTH, GAME_HEIGHT);

         // Hills
         for (const h of HILLS) {
            ctx.fillStyle = '#3aa239';
            ctx.beginPath();
            ctx.arc(h.x, GROUND_TOP, h.r, Math.PI, 2 * Math.PI);
            ctx.fill();
            ctx.fillStyle = '#2f8a30';
            ctx.beginPath();
            ctx.arc(h.x, GROUND_TOP, h.r * 0.6, Math.PI, 2 * Math.PI);
            ctx.fill();
         }

         // Clouds
         for (const cl of CLOUDS) {
            ctx.fillStyle = '#ffffff';
            const cy = cl.y;
            for (const [ox, oy, rr] of [[-26, 4, 16], [-6, -6, 22], [18, 2, 18], [0, 10, 20]] as const) {
               ctx.beginPath();
               ctx.arc(cl.x + ox * cl.s, cy + oy * cl.s, rr * cl.s, 0, Math.PI * 2);
               ctx.fill();
            }
         }

         // Bushes
         for (const b of BUSHES) {
            ctx.fillStyle = '#27a300';
            for (const [ox, rr] of [[-22, 16], [0, 22], [22, 16]] as const) {
               ctx.beginPath();
               ctx.arc(b.x + ox * b.s, GROUND_TOP, rr * b.s, Math.PI, 2 * Math.PI);
               ctx.fill();
            }
         }

         // Ground: grass strip + brick dirt
         ctx.fillStyle = '#c87f3a';
         ctx.fillRect(0, GROUND_TOP, GAME_WIDTH, GROUND_HEIGHT);
         ctx.fillStyle = '#7a431f';
         for (let bx = 0; bx < GAME_WIDTH; bx += 32) {
            for (let by = GROUND_TOP + 10; by < GAME_HEIGHT; by += 16) {
               const off = ((by - GROUND_TOP) / 16) % 2 === 0 ? 0 : 16;
               ctx.strokeStyle = '#7a431f';
               ctx.lineWidth = 2;
               ctx.strokeRect(bx + off, by, 32, 16);
            }
         }
         ctx.fillStyle = '#3aa239';
         ctx.fillRect(0, GROUND_TOP, GAME_WIDTH, 10);
         ctx.fillStyle = '#2f8a30';
         ctx.fillRect(0, GROUND_TOP + 8, GAME_WIDTH, 2);

         // Platforms: brick blocks
         for (const pf of PLATFORMS) {
            ctx.fillStyle = '#d99a3e';
            ctx.fillRect(pf.x, pf.y, pf.w, pf.h);
            ctx.fillStyle = '#a5621f';
            ctx.fillRect(pf.x, pf.y + pf.h - 5, pf.w, 5);
            ctx.strokeStyle = '#6e3d12';
            ctx.lineWidth = 2;
            ctx.strokeRect(pf.x, pf.y, pf.w, pf.h);
            for (let sx = pf.x + 22; sx < pf.x + pf.w; sx += 22) {
               ctx.beginPath();
               ctx.moveTo(sx, pf.y);
               ctx.lineTo(sx, pf.y + pf.h);
               ctx.stroke();
            }
         }

         // Coins: spinning gold
         const t = now / 1000;
         for (const c of coinsRef.current) {
            const sw = Math.abs(Math.cos(t * 4 + c.x)) * COIN_RADIUS + 2;
            ctx.fillStyle = '#f4c430';
            ctx.beginPath();
            ctx.ellipse(c.x, c.y, sw, COIN_RADIUS, 0, 0, Math.PI * 2);
            ctx.fill();
            ctx.strokeStyle = '#b8860b';
            ctx.lineWidth = 2;
            ctx.stroke();
            ctx.fillStyle = '#fff4b8';
            ctx.beginPath();
            ctx.ellipse(c.x - sw * 0.3, c.y - 2, sw * 0.25, COIN_RADIUS * 0.45, 0, 0, Math.PI * 2);
            ctx.fill();
         }

         // Player character (borgo-colored body, cap, walking feet, emoji face)
         const px = p.x, py = p.y;
         const cx = px + PLAYER_W / 2;
         const moving = Math.abs(p.vx) > 1 && p.onGround;
         const legStep = moving ? (Math.floor(px / 7) % 2 === 0 ? 1 : -1) : 0;

         // Shadow
         ctx.fillStyle = 'rgba(0,0,0,0.18)';
         ctx.beginPath();
         ctx.ellipse(cx, GROUND_TOP + 4, PLAYER_W * 0.55, 5, 0, 0, Math.PI * 2);
         ctx.fill();

         // Feet
         ctx.fillStyle = '#5b3a1a';
         ctx.fillRect(px + 3, py + PLAYER_H - 4 + (legStep > 0 ? -2 : 0), 9, 6);
         ctx.fillRect(px + PLAYER_W - 12, py + PLAYER_H - 4 + (legStep < 0 ? -2 : 0), 9, 6);

         // Body
         const r = 7;
         ctx.fillStyle = borgoColor;
         ctx.beginPath();
         ctx.moveTo(px + r, py + 6);
         ctx.arcTo(px + PLAYER_W, py + 6, px + PLAYER_W, py + PLAYER_H, r);
         ctx.arcTo(px + PLAYER_W, py + PLAYER_H, px, py + PLAYER_H, r);
         ctx.arcTo(px, py + PLAYER_H, px, py + 6, r);
         ctx.arcTo(px, py + 6, px + PLAYER_W, py + 6, r);
         ctx.closePath();
         ctx.fill();
         ctx.lineWidth = 2;
         ctx.strokeStyle = 'rgba(0,0,0,0.35)';
         ctx.stroke();

         // Cap
         ctx.fillStyle = 'rgba(0,0,0,0.45)';
         ctx.beginPath();
         ctx.moveTo(px - 1, py + 8);
         ctx.quadraticCurveTo(cx, py - 9, px + PLAYER_W + 1, py + 8);
         ctx.lineTo(px + PLAYER_W + 1, py + 12);
         ctx.lineTo(px - 1, py + 12);
         ctx.closePath();
         ctx.fill();
         // Cap brim points the way the player faces
         ctx.beginPath();
         if (p.facing >= 0) {
            ctx.moveTo(px + PLAYER_W - 2, py + 9);
            ctx.lineTo(px + PLAYER_W + 9, py + 11);
            ctx.lineTo(px + PLAYER_W - 2, py + 13);
         } else {
            ctx.moveTo(px + 2, py + 9);
            ctx.lineTo(px - 9, py + 11);
            ctx.lineTo(px + 2, py + 13);
         }
         ctx.closePath();
         ctx.fill();

         // Emoji face
         ctx.font = '18px serif';
         ctx.textAlign = 'center';
         ctx.textBaseline = 'middle';
         ctx.fillText(borgoEmoji, cx, py + 26);

         raf = requestAnimationFrame(step);
      };

      raf = requestAnimationFrame(step);
      return () => cancelAnimationFrame(raf);
   }, [selectedBorgo, borgoColor, borgoEmoji]);

   // Keyboard input
   useEffect(() => {
      const down = (e: KeyboardEvent) => {
         if (['ArrowLeft', 'ArrowRight', 'ArrowUp', ' '].includes(e.key)) e.preventDefault();
         keysRef.current[e.key] = true;
      };
      const up = (e: KeyboardEvent) => {
         keysRef.current[e.key] = false;
      };
      window.addEventListener('keydown', down);
      window.addEventListener('keyup', up);
      return () => {
         window.removeEventListener('keydown', down);
         window.removeEventListener('keyup', up);
      };
   }, []);

   const holdStart = (e: React.PointerEvent, key: string) => {
      e.preventDefault();
      try {
         (e.currentTarget as HTMLElement).setPointerCapture(e.pointerId);
      } catch {
         /* not supported */
      }
      keysRef.current[key] = true;
   };
   const holdEnd = (key: string) => {
      keysRef.current[key] = false;
   };
   const noSelect = {
      userSelect: 'none',
      WebkitUserSelect: 'none',
      WebkitTouchCallout: 'none',
      touchAction: 'manipulation',
   } as const;

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

   return (
      <Container maxWidth="lg">
         <Box sx={{mt: 4, mb: 4}}>
            <Box sx={{display: 'flex', justifyContent: 'space-between', alignItems: 'center', mb: 3}}>
               <Typography variant="h4" component="h1">
                  Gioco
               </Typography>
               <YearSelector/>
            </Box>

            {!selectedBorgo ? (
               <Card>
                  <CardContent>
                     <Typography variant="h6" gutterBottom>
                        Scegli il tuo borgo
                     </Typography>
                     <Typography variant="body2" color="text.secondary" sx={{mb: 3}}>
                        Muoviti a destra e sinistra, salta e raccogli più monete che puoi!
                     </Typography>
                     <FormControl sx={{minWidth: 240}}>
                        <InputLabel id="borgo-select-label">Borgo</InputLabel>
                        <Select
                           labelId="borgo-select-label"
                           label="Borgo"
                           value=""
                           onChange={(e) => startWithBorgo(e.target.value as string)}
                        >
                           {villages.map((v) => (
                              <MenuItem key={v} value={v}>
                                 {BORGO_EMOJIS[villages.indexOf(v) % BORGO_EMOJIS.length]} {v}
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
               <Card sx={noSelect}>
                  <CardContent>
                     <Box sx={{display: 'flex', justifyContent: 'space-between', alignItems: 'center', mb: 2}}>
                        <Typography variant="h6">
                           {borgoEmoji} {selectedBorgo} — Monete: {score}
                        </Typography>
                        <Stack direction="row" spacing={1}>
                           <Button variant="outlined" size="small" onClick={resetGame}>
                              Ricomincia
                           </Button>
                           <Button variant="text" size="small" onClick={() => setSelectedBorgo(null)}>
                              Cambia borgo
                           </Button>
                        </Stack>
                     </Box>

                     <Box
                        sx={{
                           width: '100%',
                           display: 'flex',
                           justifyContent: 'center',
                           userSelect: 'none',
                        }}
                     >
                        <canvas
                           ref={canvasRef}
                           width={GAME_WIDTH}
                           height={GAME_HEIGHT}
                           onContextMenu={(e) => e.preventDefault()}
                           style={{
                              width: '100%',
                              maxWidth: GAME_WIDTH,
                              height: 'auto',
                              borderRadius: 8,
                              border: '1px solid rgba(255,255,255,0.15)',
                              touchAction: 'none',
                              userSelect: 'none',
                              WebkitUserSelect: 'none',
                              WebkitTouchCallout: 'none',
                           }}
                        />
                     </Box>

                     <Typography variant="caption" color="text.secondary" sx={{display: 'block', mt: 1}}>
                        Controlli: ← → per muoverti, Spazio / ↑ per saltare
                     </Typography>

                     {/* Touch controls for mobile */}
                     <Stack
                        direction="row"
                        spacing={2}
                        sx={{mt: 2, justifyContent: 'center', ...noSelect}}
                     >
                        <Button
                           variant="contained"
                           disableRipple
                           onContextMenu={(e) => e.preventDefault()}
                           onPointerDown={(e) => holdStart(e, 'ArrowLeft')}
                           onPointerUp={() => holdEnd('ArrowLeft')}
                           onPointerLeave={() => holdEnd('ArrowLeft')}
                           onPointerCancel={() => holdEnd('ArrowLeft')}
                           sx={{minWidth: 64, ...noSelect}}
                        >
                           ←
                        </Button>
                        <Button
                           variant="contained"
                           disableRipple
                           onContextMenu={(e) => e.preventDefault()}
                           onPointerDown={(e) => holdStart(e, ' ')}
                           onPointerUp={() => holdEnd(' ')}
                           onPointerLeave={() => holdEnd(' ')}
                           onPointerCancel={() => holdEnd(' ')}
                           sx={{minWidth: 96, ...noSelect}}
                        >
                           Salta
                        </Button>
                        <Button
                           variant="contained"
                           disableRipple
                           onContextMenu={(e) => e.preventDefault()}
                           onPointerDown={(e) => holdStart(e, 'ArrowRight')}
                           onPointerUp={() => holdEnd('ArrowRight')}
                           onPointerLeave={() => holdEnd('ArrowRight')}
                           onPointerCancel={() => holdEnd('ArrowRight')}
                           sx={{minWidth: 64, ...noSelect}}
                        >
                           →
                        </Button>
                     </Stack>
                  </CardContent>
               </Card>
            )}
         </Box>
      </Container>
   );
};

export default ArcadeGamePage;
