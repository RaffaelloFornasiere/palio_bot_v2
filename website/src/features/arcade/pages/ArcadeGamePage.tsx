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

// Green pipes (you can stand on top; classic SMB obstacle).
const PIPE_W = 56;
const PIPES = [
   {x: 360, h: 64},
   {x: 690, h: 48},
];

const GOOMBA_W = 28;
const GOOMBA_H = 26;
const GOOMBA_SPEED = 55;

interface Goomba {
   x: number;
   y: number;
   dir: number;
   alive: boolean;
}

// Authentic-ish Super Mario Bros. palette.
const C = {
   sky: '#5c94fc',
   brick: '#c84c0c',
   brickHi: '#fc9838',
   mortar: '#000000',
   block: '#fac000',
   blockEdge: '#e45c10',
   pipe: '#00a800',
   pipeHi: '#80d010',
   pipeDark: '#007800',
   green: '#00a800',
   greenHi: '#80d010',
   greenDark: '#007800',
   white: '#ffffff',
   coin: '#fac000',
   coinHi: '#fff4b8',
   coinEdge: '#b86010',
   goomba: '#b86010',
   goombaFoot: '#000000',
   skin: '#f8b080',
   eye: '#000000',
   boot: '#5b3a1a',
};

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
   const goombasRef = useRef<Goomba[]>([]);
   const scoreRef = useRef(0);

   const makeGoombas = (): Goomba[] => [
      {x: 300, y: GROUND_TOP - GOOMBA_H, dir: -1, alive: true},
      {x: 560, y: GROUND_TOP - GOOMBA_H, dir: 1, alive: true},
   ];

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
      goombasRef.current = makeGoombas();
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
      ctx.imageSmoothingEnabled = false;
      if (goombasRef.current.length === 0) goombasRef.current = makeGoombas();

      // Pipe collision tops (stand on the pipe rim).
      const pipeTops: Rect[] = PIPES.map((pp) => ({
         x: pp.x, y: GROUND_TOP - pp.h, w: PIPE_W, h: pp.h,
      }));

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

         const solids: Rect[] = [
            {x: 0, y: GROUND_TOP, w: GAME_WIDTH, h: GROUND_HEIGHT},
            ...PLATFORMS,
            ...pipeTops,
         ];
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

         // Goombas: patrol the ground, get stomped, or knock the player back
         for (const g of goombasRef.current) {
            if (!g.alive) continue;
            g.x += g.dir * GOOMBA_SPEED * dt;
            if (g.x < 30) {
               g.x = 30;
               g.dir = 1;
            } else if (g.x > GAME_WIDTH - 30 - GOOMBA_W) {
               g.x = GAME_WIDTH - 30 - GOOMBA_W;
               g.dir = -1;
            }
            const overlap =
               p.x + PLAYER_W > g.x &&
               p.x < g.x + GOOMBA_W &&
               p.y + PLAYER_H > g.y &&
               p.y < g.y + GOOMBA_H;
            if (overlap) {
               if (p.vy > 0 && prevBottom <= g.y + 10) {
                  g.alive = false;
                  scoreRef.current += 2;
                  setScore(scoreRef.current);
                  p.vy = -380;
               } else {
                  p.x = 80;
                  p.y = GROUND_TOP - PLAYER_H;
                  p.vx = 0;
                  p.vy = 0;
               }
            }
         }

         // ---- Draw (pixel-art Super Mario Bros. style) ----
         const t = now / 1000;
         const R = Math.round;

         // Sky
         ctx.fillStyle = C.sky;
         ctx.fillRect(0, 0, GAME_WIDTH, GAME_HEIGHT);

         // Clouds (blocky, scalloped)
         for (const cl of CLOUDS) {
            const w = R(60 * cl.s), bx = R(cl.x - w / 2), by = R(cl.y);
            ctx.fillStyle = '#3cbcfc';
            ctx.fillRect(bx - 2, by + 12, w + 4, 16);
            ctx.fillStyle = C.white;
            ctx.fillRect(bx, by + 10, w, 14);
            ctx.fillRect(bx + 8, by, 16, 14);
            ctx.fillRect(bx + w - 26, by + 2, 18, 12);
            ctx.fillRect(R(bx + w / 2 - 8), by - 6, 18, 16);
         }

         // Hills (stacked green blocks)
         for (const h of HILLS) {
            for (let i = 0; i < 5; i++) {
               const ww = R(h.r * 2 - i * h.r * 0.34);
               const hh = 13;
               const hx = R(h.x - ww / 2);
               const hy = GROUND_TOP - (i + 1) * hh;
               ctx.fillStyle = C.green;
               ctx.fillRect(hx, hy, ww, hh);
               ctx.fillStyle = C.greenHi;
               ctx.fillRect(hx + 4, hy + 2, 6, 3);
               ctx.fillStyle = C.greenDark;
               ctx.fillRect(hx, hy + hh - 2, ww, 2);
            }
         }

         // Bushes
         for (const b of BUSHES) {
            const s = b.s;
            ctx.fillStyle = C.green;
            ctx.fillRect(R(b.x - 30 * s), GROUND_TOP - 16, R(60 * s), 16);
            ctx.fillRect(R(b.x - 18 * s), GROUND_TOP - 24, R(20 * s), 24);
            ctx.fillRect(R(b.x + 2 * s), GROUND_TOP - 22, R(16 * s), 22);
            ctx.fillStyle = C.greenDark;
            ctx.fillRect(R(b.x - 30 * s), GROUND_TOP - 2, R(60 * s), 2);
         }

         // Pipes
         for (const pp of PIPES) {
            const ptop = GROUND_TOP - pp.h;
            ctx.fillStyle = C.pipe;
            ctx.fillRect(pp.x + 4, ptop + 16, PIPE_W - 8, pp.h - 16);
            ctx.fillStyle = C.pipeHi;
            ctx.fillRect(pp.x + 8, ptop + 16, 8, pp.h - 16);
            ctx.fillStyle = C.pipeDark;
            ctx.fillRect(pp.x + PIPE_W - 12, ptop + 16, 8, pp.h - 16);
            ctx.fillStyle = C.pipe;
            ctx.fillRect(pp.x - 4, ptop, PIPE_W + 8, 16);
            ctx.fillStyle = C.pipeHi;
            ctx.fillRect(pp.x, ptop + 3, 10, 10);
            ctx.fillStyle = C.pipeDark;
            ctx.fillRect(pp.x + PIPE_W - 6, ptop, 10, 16);
            ctx.fillStyle = C.mortar;
            ctx.fillRect(pp.x - 4, ptop, PIPE_W + 8, 2);
         }

         // Ground (orange brick tiles)
         for (let gx = 0; gx < GAME_WIDTH; gx += 16) {
            for (let gy = GROUND_TOP; gy < GAME_HEIGHT; gy += 16) {
               ctx.fillStyle = C.brick;
               ctx.fillRect(gx, gy, 16, 16);
               ctx.fillStyle = C.brickHi;
               ctx.fillRect(gx + 1, gy + 1, 14, 3);
               ctx.fillStyle = C.mortar;
               ctx.fillRect(gx + 15, gy, 1, 16);
               ctx.fillRect(gx, gy + 15, 16, 1);
            }
         }

         // Platforms (golden ? blocks)
         for (const pf of PLATFORMS) {
            for (let qx = pf.x; qx < pf.x + pf.w - 1; qx += pf.h) {
               const bw = Math.min(pf.h, pf.x + pf.w - qx);
               ctx.fillStyle = C.block;
               ctx.fillRect(qx, pf.y, bw, pf.h);
               ctx.fillStyle = C.blockEdge;
               ctx.fillRect(qx, pf.y, bw, 3);
               ctx.fillRect(qx, pf.y, 3, pf.h);
               ctx.fillRect(qx, pf.y + pf.h - 3, bw, 3);
               ctx.fillRect(qx + bw - 3, pf.y, 3, pf.h);
               ctx.fillStyle = C.mortar;
               ctx.fillRect(qx + 4, pf.y + 4, 2, 2);
               ctx.fillRect(qx + bw - 6, pf.y + 4, 2, 2);
               ctx.fillRect(qx + 4, pf.y + pf.h - 6, 2, 2);
               ctx.fillRect(qx + bw - 6, pf.y + pf.h - 6, 2, 2);
               ctx.fillStyle = C.coinHi;
               ctx.fillRect(R(qx + bw / 2 - 2), R(pf.y + pf.h / 2 - 2), 4, 4);
            }
         }

         // Coins (blocky spinning)
         for (const c of coinsRef.current) {
            const sw = R(Math.abs(Math.cos(t * 6 + c.x)) * 7) + 4;
            const ck = R(c.x), cyk = R(c.y);
            ctx.fillStyle = C.coinEdge;
            ctx.fillRect(ck - sw, cyk - 10, sw * 2, 20);
            ctx.fillStyle = C.coin;
            ctx.fillRect(ck - sw + 2, cyk - 9, Math.max(1, sw * 2 - 4), 18);
            ctx.fillStyle = C.coinHi;
            ctx.fillRect(ck - 1, cyk - 7, Math.max(1, R(sw / 2)), 14);
         }

         // Goombas
         for (const g of goombasRef.current) {
            if (!g.alive) continue;
            const gx = R(g.x), gy = R(g.y);
            const wob = Math.floor(t * 6) % 2 === 0 ? 0 : 2;
            ctx.fillStyle = C.goomba;
            ctx.fillRect(gx + 2, gy, GOOMBA_W - 4, 6);
            ctx.fillRect(gx, gy + 6, GOOMBA_W, GOOMBA_H - 12);
            ctx.fillStyle = '#f4d8b0';
            ctx.fillRect(gx + 4, gy + GOOMBA_H - 12, GOOMBA_W - 8, 6);
            ctx.fillStyle = C.white;
            ctx.fillRect(gx + 5, gy + 8, 6, 7);
            ctx.fillRect(gx + GOOMBA_W - 11, gy + 8, 6, 7);
            ctx.fillStyle = C.eye;
            ctx.fillRect(gx + 8, gy + 9, 3, 5);
            ctx.fillRect(gx + GOOMBA_W - 8, gy + 9, 3, 5);
            ctx.fillRect(gx + 4, gy + 6, 8, 2);
            ctx.fillRect(gx + GOOMBA_W - 12, gy + 6, 8, 2);
            ctx.fillStyle = C.goombaFoot;
            ctx.fillRect(gx + 1, gy + GOOMBA_H - 5 - wob, 11, 5);
            ctx.fillRect(gx + GOOMBA_W - 12, gy + GOOMBA_H - 5 - (2 - wob), 11, 5);
         }

         // Player (pixel-art, suit tinted with the borgo color)
         const px = R(p.x), py = R(p.y);
         const cx = px + PLAYER_W / 2;
         const f = p.facing >= 0 ? 1 : -1;
         const moving = Math.abs(p.vx) > 1 && p.onGround;
         const phase = moving ? Math.floor(p.x / 6) % 2 : -1;
         const air = !p.onGround;

         ctx.fillStyle = 'rgba(0,0,0,0.18)';
         ctx.fillRect(px + 2, GROUND_TOP - 2, PLAYER_W - 4, 3);

         ctx.fillStyle = C.boot;
         if (air) {
            ctx.fillRect(px + 4, py + PLAYER_H - 7, 9, 7);
            ctx.fillRect(px + PLAYER_W - 13, py + PLAYER_H - 9, 9, 7);
         } else if (phase === 0) {
            ctx.fillRect(px + 2, py + PLAYER_H - 5, 10, 5);
            ctx.fillRect(px + PLAYER_W - 12, py + PLAYER_H - 5, 10, 5);
         } else if (phase === 1) {
            ctx.fillRect(px + 5, py + PLAYER_H - 5, 10, 5);
            ctx.fillRect(px + PLAYER_W - 15, py + PLAYER_H - 5, 10, 5);
         } else {
            ctx.fillRect(px + 4, py + PLAYER_H - 5, 9, 5);
            ctx.fillRect(px + PLAYER_W - 13, py + PLAYER_H - 5, 9, 5);
         }

         ctx.fillStyle = borgoColor;
         ctx.fillRect(px + 4, py + 24, PLAYER_W - 8, PLAYER_H - 28);
         ctx.fillRect(px + 3, py + 16, PLAYER_W - 6, 10);

         const armY = py + 17 + (moving && phase === 1 ? 2 : 0);
         ctx.fillRect(px - 1, armY, 5, 8);
         ctx.fillRect(px + PLAYER_W - 4, armY, 5, 8);
         ctx.fillStyle = C.skin;
         ctx.fillRect(px - 1, armY + 8, 5, 3);
         ctx.fillRect(px + PLAYER_W - 4, armY + 8, 5, 3);

         ctx.fillStyle = C.skin;
         ctx.fillRect(px + 7, py + 6, PLAYER_W - 14, 11);
         ctx.fillStyle = C.eye;
         ctx.fillRect(f > 0 ? px + PLAYER_W - 12 : px + 9, py + 9, 3, 4);
         ctx.fillRect(px + 8, py + 14, PLAYER_W - 16, 3);

         ctx.fillStyle = borgoColor;
         ctx.fillRect(px + 5, py + 1, PLAYER_W - 10, 6);
         ctx.fillRect(px + 7, py - 2, PLAYER_W - 14, 4);
         if (f > 0) ctx.fillRect(px + PLAYER_W - 8, py + 5, 10, 3);
         else ctx.fillRect(px - 2, py + 5, 10, 3);
         ctx.fillStyle = C.mortar;
         ctx.fillRect(px + 5, py + 6, PLAYER_W - 10, 1);
         ctx.fillStyle = C.white;
         ctx.fillRect(R(cx - 2), py + 2, 4, 3);

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
