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
   {x: 160, y: 290, w: 150, h: 14},
   {x: 400, y: 225, w: 150, h: 14},
   {x: 600, y: 300, w: 130, h: 14},
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
   const playerRef = useRef({x: 80, y: GROUND_TOP - PLAYER_H, vx: 0, vy: 0, onGround: true});
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
      playerRef.current = {x: 80, y: GROUND_TOP - PLAYER_H, vx: 0, vy: 0, onGround: true};
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
         const sky = ctx.createLinearGradient(0, 0, 0, GAME_HEIGHT);
         sky.addColorStop(0, '#0d1b2a');
         sky.addColorStop(1, '#1b263b');
         ctx.fillStyle = sky;
         ctx.fillRect(0, 0, GAME_WIDTH, GAME_HEIGHT);

         // Ground
         ctx.fillStyle = '#3a2e1f';
         ctx.fillRect(0, GROUND_TOP, GAME_WIDTH, GROUND_HEIGHT);
         ctx.fillStyle = '#4caf50';
         ctx.fillRect(0, GROUND_TOP, GAME_WIDTH, 6);

         // Platforms
         ctx.fillStyle = borgoColor;
         for (const pf of PLATFORMS) {
            ctx.fillRect(pf.x, pf.y, pf.w, pf.h);
         }

         // Coins
         for (const c of coinsRef.current) {
            ctx.beginPath();
            ctx.arc(c.x, c.y, COIN_RADIUS, 0, Math.PI * 2);
            ctx.fillStyle = '#ffd54f';
            ctx.fill();
            ctx.lineWidth = 2;
            ctx.strokeStyle = '#f9a825';
            ctx.stroke();
         }

         // Player token
         ctx.fillStyle = borgoColor;
         const r = 6;
         const px = p.x, py = p.y;
         ctx.beginPath();
         ctx.moveTo(px + r, py);
         ctx.arcTo(px + PLAYER_W, py, px + PLAYER_W, py + PLAYER_H, r);
         ctx.arcTo(px + PLAYER_W, py + PLAYER_H, px, py + PLAYER_H, r);
         ctx.arcTo(px, py + PLAYER_H, px, py, r);
         ctx.arcTo(px, py, px + PLAYER_W, py, r);
         ctx.closePath();
         ctx.fill();
         ctx.lineWidth = 2;
         ctx.strokeStyle = 'rgba(255,255,255,0.7)';
         ctx.stroke();
         ctx.font = '22px serif';
         ctx.textAlign = 'center';
         ctx.textBaseline = 'middle';
         ctx.fillText(borgoEmoji, px + PLAYER_W / 2, py + PLAYER_H / 2 + 1);

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

   const setKey = (key: string, value: boolean) => {
      keysRef.current[key] = value;
   };

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
               <Card>
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
                           style={{
                              width: '100%',
                              maxWidth: GAME_WIDTH,
                              height: 'auto',
                              borderRadius: 8,
                              border: '1px solid rgba(255,255,255,0.15)',
                              touchAction: 'none',
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
                        sx={{mt: 2, justifyContent: 'center'}}
                     >
                        <Button
                           variant="contained"
                           onPointerDown={() => setKey('ArrowLeft', true)}
                           onPointerUp={() => setKey('ArrowLeft', false)}
                           onPointerLeave={() => setKey('ArrowLeft', false)}
                           sx={{minWidth: 64}}
                        >
                           ←
                        </Button>
                        <Button
                           variant="contained"
                           onPointerDown={() => setKey(' ', true)}
                           onPointerUp={() => setKey(' ', false)}
                           onPointerLeave={() => setKey(' ', false)}
                           sx={{minWidth: 96}}
                        >
                           Salta
                        </Button>
                        <Button
                           variant="contained"
                           onPointerDown={() => setKey('ArrowRight', true)}
                           onPointerUp={() => setKey('ArrowRight', false)}
                           onPointerLeave={() => setKey('ArrowRight', false)}
                           sx={{minWidth: 64}}
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
