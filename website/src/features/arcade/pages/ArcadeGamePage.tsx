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
} from '@mui/material';
import {PalioData} from '../../../generated/types.gen';
import {getPalioDataForYear} from '../../../utils/yearApi';
import {useYear} from '../../../contexts/YearContext';
import YearSelector from '../../../components/YearSelector';

// ---- Authentic-ish NES Super Mario Bros palette ----
const SKY = '#5C94FC';
const GROUND = '#C84C0C';
const GROUND_DARK = '#7C2C00';
const GROUND_TOP = '#E45C10';
const BRICK = '#C84C0C';
const BRICK_LINE = '#000000';
const QBLOCK = '#FAC000';
const QBLOCK_DARK = '#B86010';
const QBLOCK_USED = '#9C5C30';
const PIPE = '#00A800';
const PIPE_LIGHT = '#80D010';
const PIPE_DARK = '#006000';
const HILL = '#00A800';
const HILL_DARK = '#007000';
const CLOUD = '#FCFCFC';
const COIN = '#FAC000';
const COIN_DARK = '#B86010';
const GOOMBA = '#9C4A00';
const GOOMBA_FOOT = '#000000';
const SKIN = '#FCBC8C';
const OVERALLS = '#0058F8';
const SHOE = '#7C2C00';

const TILE = 32;
const VIEW_W = TILE * 17; // 544
const VIEW_H = TILE * 14; // 448

const GRAVITY = 2400;
const WALK_ACCEL = 1100;
const RUN_MAX = 380;
const WALK_MAX = 230;
const FRICTION = 1500;
const JUMP_V = -780;
const JUMP_CUT = 0.45; // releasing jump early shortens the hop
const MAX_FALL = 900;
const GOOMBA_SPEED = 55;
const START_TIME = 300;

const P_W = 24;
const P_H = 30;

// Compact but iconic level. Rows top->bottom, 14 tall. '.' empty,
// 'X' solid ground/block, 'B' brick, '?' question (coin), 'o' coin,
// 'g' goomba, 'p' pipe (top-left anchor; height by stacked 'p'),
// '|' pipe body, 'F' flag base. Bottom 2 rows are ground (with pits).
const LEVEL: string[] = [
   '.............................................................................................',
   '.............................................................................................',
   '.............................................................................................',
   '...........................o.o.o.............................................................',
   '..................?.......BBB?BBB..................o.o........................................',
   '.............................................................B?B.............................',
   '..............................................p.............................................',
   '............?...B?B?B.....g........g..........p|.......g....g.................F...............',
   '.......................................p.....p|.............................XF...............',
   '......................g................p|....p|.....g......................XXF...............',
   '....g................................p.p|....p|...........................XXXF...............',
   '..................................p..p.p|....p|.........................XXXXF.....C..........',
   'XXXXXXXXX...XXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXX...XXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXX',
   'XXXXXXXXX...XXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXX...XXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXX',
];

type Solid = {x: number; y: number; w: number; h: number};
interface Block extends Solid {
   kind: 'ground' | 'brick' | 'question' | 'pipe';
   used?: boolean;
   bump?: number; // animation offset when hit from below
}
interface Coin {x: number; y: number; t: number; got?: boolean}
interface Goomba {x: number; y: number; vx: number; vy: number; w: number; h: number; dead: number; alive: boolean}

const ArcadeGamePage: React.FC = () => {
   const [palioData, setPalioData] = useState<PalioData | null>(null);
   const [loading, setLoading] = useState(true);
   const [error, setError] = useState<string | null>(null);
   const [selectedBorgo, setSelectedBorgo] = useState<string | null>(null);
   const [hud, setHud] = useState({coins: 0, score: 0, lives: 3, time: START_TIME});
   const [status, setStatus] = useState<'playing' | 'dead' | 'gameover' | 'clear'>('playing');
   const [runKey, setRunKey] = useState(0);
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

   const borgoColor: string = (selectedBorgo
      ? (palioData?.villages_colors as Record<string, string> | undefined)?.[selectedBorgo]
      : undefined) ?? '#E03030';

   const startWithBorgo = (borgo: string) => {
      setSelectedBorgo(borgo);
      setHud({coins: 0, score: 0, lives: 3, time: START_TIME});
      setStatus('playing');
      setRunKey((k) => k + 1);
   };

   const restart = useCallback(() => {
      setHud({coins: 0, score: 0, lives: 3, time: START_TIME});
      setStatus('playing');
      setRunKey((k) => k + 1);
   }, []);

   // ---- The game ----
   useEffect(() => {
      if (!selectedBorgo || status !== 'playing') return;
      const canvas = canvasRef.current;
      if (!canvas) return;
      const ctx = canvas.getContext('2d');
      if (!ctx) return;

      const levelW = LEVEL[0].length * TILE;
      const blocks: Block[] = [];
      const coins: Coin[] = [];
      const goombas: Goomba[] = [];
      let flagX = levelW - TILE * 3;

      LEVEL.forEach((row, r) => {
         for (let c = 0; c < row.length; c++) {
            const ch = row[c];
            const x = c * TILE;
            const y = r * TILE;
            if (ch === 'X') blocks.push({x, y, w: TILE, h: TILE, kind: 'ground'});
            else if (ch === 'B') blocks.push({x, y, w: TILE, h: TILE, kind: 'brick'});
            else if (ch === '?') blocks.push({x, y, w: TILE, h: TILE, kind: 'question'});
            else if (ch === 'p' || ch === '|')
               blocks.push({x, y, w: TILE, h: TILE, kind: 'pipe'});
            else if (ch === 'o') coins.push({x: x + TILE / 2, y: y + TILE / 2, t: Math.random() * 6});
            else if (ch === 'g')
               goombas.push({x, y: y + TILE - 26, vx: -GOOMBA_SPEED, vy: 0, w: 26, h: 26, dead: 0, alive: true});
            else if (ch === 'F') flagX = x;
         }
      });

      const startPos = {x: TILE * 2, y: VIEW_H - TILE * 2 - P_H};
      const p = {
         x: startPos.x, y: startPos.y, vx: 0, vy: 0,
         onGround: false, face: 1, walkT: 0, dead: false, deadT: 0, win: false, winT: 0,
      };
      let cameraX = 0;
      let time = START_TIME;
      let timeAcc = 0;
      let coinCount = hud.coins;
      let score = hud.score;
      const lives = hud.lives;

      const aabb = (ax: number, ay: number, aw: number, ah: number, b: Solid) =>
         ax < b.x + b.w && ax + aw > b.x && ay < b.y + b.h && ay + ah > b.y;

      let raf = 0;
      let last = performance.now();

      const die = () => {
         if (p.dead) return;
         p.dead = true;
         p.vy = -560;
         p.deadT = 0;
      };

      const step = (now: number) => {
         const dt = Math.min((now - last) / 1000, 0.033);
         last = now;

         // ---------- update ----------
         if (p.win) {
            p.winT += dt;
            // slide down flag then walk into castle
            if (p.y + P_H < VIEW_H - TILE * 2) p.y += 180 * dt;
            else p.x += 90 * dt;
            if (p.winT > 2.4) {
               setHud({coins: coinCount, score, lives, time: Math.ceil(time)});
               setStatus('clear');
               return;
            }
         } else if (p.dead) {
            p.deadT += dt;
            p.vy = Math.min(p.vy + GRAVITY * dt, MAX_FALL);
            p.y += p.vy * dt;
            if (p.deadT > 1.3) {
               const remaining = lives - 1;
               if (remaining <= 0) {
                  setHud({coins: coinCount, score, lives: 0, time: Math.ceil(time)});
                  setStatus('gameover');
                  return;
               }
               setHud({coins: coinCount, score, lives: remaining, time: START_TIME});
               setStatus('dead');
               return;
            }
         } else {
            timeAcc += dt;
            if (timeAcc >= 1) {
               timeAcc -= 1;
               time -= 1;
               if (time <= 0) {
                  die();
               }
            }

            const k = keys.current;
            const left = k['ArrowLeft'] || k['a'];
            const right = k['ArrowRight'] || k['d'];
            const running = k['Shift'] || k['x'];
            const jumpHeld = k['ArrowUp'] || k['w'] || k[' '] || k['z'];
            const maxSpeed = running ? RUN_MAX : WALK_MAX;

            if (left && !right) {
               p.vx -= WALK_ACCEL * dt;
               p.face = -1;
            } else if (right && !left) {
               p.vx += WALK_ACCEL * dt;
               p.face = 1;
            } else {
               const f = FRICTION * dt;
               if (p.vx > f) p.vx -= f;
               else if (p.vx < -f) p.vx += f;
               else p.vx = 0;
            }
            p.vx = Math.max(-maxSpeed, Math.min(maxSpeed, p.vx));

            if (jumpHeld && p.onGround) {
               p.vy = JUMP_V;
               p.onGround = false;
            }
            if (!jumpHeld && p.vy < 0) p.vy *= 1 - JUMP_CUT * Math.min(1, dt * 60);

            p.vy = Math.min(p.vy + GRAVITY * dt, MAX_FALL);

            // ---- horizontal move + collide ----
            p.x += p.vx * dt;
            if (p.x < 0) {
               p.x = 0;
               p.vx = 0;
            }
            for (const b of blocks) {
               if (aabb(p.x, p.y, P_W, P_H, b)) {
                  if (p.vx > 0) p.x = b.x - P_W;
                  else if (p.vx < 0) p.x = b.x + b.w;
                  p.vx = 0;
               }
            }

            // ---- vertical move + collide ----
            p.y += p.vy * dt;
            p.onGround = false;
            for (const b of blocks) {
               if (aabb(p.x, p.y, P_W, P_H, b)) {
                  if (p.vy > 0) {
                     p.y = b.y - P_H;
                     p.vy = 0;
                     p.onGround = true;
                  } else if (p.vy < 0) {
                     p.y = b.y + b.h;
                     p.vy = 0;
                     if (b.kind === 'question' && !b.used) {
                        b.used = true;
                        b.bump = 8;
                        coinCount += 1;
                        score += 200;
                        if (coinCount >= 100) {
                           coinCount = 0;
                        }
                     } else if (b.kind === 'brick' || b.kind === 'ground') {
                        b.bump = 6;
                     }
                  }
               }
            }
            blocks.forEach((b) => {
               if (b.bump && b.bump > 0) b.bump = Math.max(0, b.bump - 60 * dt);
            });

            // walk animation
            if (Math.abs(p.vx) > 10 && p.onGround) p.walkT += dt * Math.abs(p.vx) * 0.04;
            else p.walkT = 0;

            // pit / fall death
            if (p.y > VIEW_H + 80) die();

            // flag
            if (!p.win && p.x + P_W > flagX && p.x < flagX + TILE) {
               p.win = true;
               p.vx = 0;
               p.vy = 0;
               score += Math.ceil(time) * 10;
               p.x = flagX - 2;
            }

            // ---- goombas ----
            for (const g of goombas) {
               if (!g.alive) {
                  if (g.dead > 0) g.dead -= dt;
                  continue;
               }
               g.vy = Math.min(g.vy + GRAVITY * dt, MAX_FALL);
               g.x += g.vx * dt;
               // turn at walls
               for (const b of blocks) {
                  if (aabb(g.x, g.y, g.w, g.h, b)) {
                     if (g.vx > 0) g.x = b.x - g.w;
                     else g.x = b.x + b.w;
                     g.vx = -g.vx;
                  }
               }
               g.y += g.vy * dt;
               for (const b of blocks) {
                  if (aabb(g.x, g.y, g.w, g.h, b)) {
                     if (g.vy > 0) {
                        g.y = b.y - g.h;
                        g.vy = 0;
                     }
                  }
               }
               if (g.y > VIEW_H + 80) g.alive = false;

               // player vs goomba
               if (!p.dead && !p.win && aabb(p.x, p.y, P_W, P_H, g)) {
                  const stomp = p.vy > 0 && p.y + P_H - g.y < 16;
                  if (stomp) {
                     g.alive = false;
                     g.dead = 0.5;
                     p.vy = -420;
                     score += 100;
                  } else {
                     die();
                  }
               }
            }

            // ---- coins ----
            for (const c of coins) {
               if (c.got) continue;
               c.t += dt * 6;
               if (aabb(p.x, p.y, P_W, P_H, {x: c.x - 10, y: c.y - 14, w: 20, h: 28})) {
                  c.got = true;
                  coinCount += 1;
                  score += 200;
                  if (coinCount >= 100) coinCount = 0;
               }
            }
         }

         // camera
         const target = p.x - VIEW_W * 0.38;
         cameraX = Math.max(0, Math.min(levelW - VIEW_W, Math.max(cameraX, target)));

         setHud((h) =>
            h.coins === coinCount && h.score === score && h.time === Math.ceil(time)
               ? h
               : {coins: coinCount, score, lives, time: Math.max(0, Math.ceil(time))},
         );

         // ---------- draw ----------
         ctx.fillStyle = SKY;
         ctx.fillRect(0, 0, VIEW_W, VIEW_H);

         ctx.save();
         ctx.translate(-Math.round(cameraX), 0);

         // background: hills + clouds + bushes (parallax-light)
         const groundY = VIEW_H - TILE * 2;
         drawHill(ctx, 120, groundY, 1.4);
         drawHill(ctx, 760, groundY, 1.0);
         drawHill(ctx, 1700, groundY, 1.4);
         drawHill(ctx, 2500, groundY, 1.0);
         drawCloud(ctx, 260, 70, 1);
         drawCloud(ctx, 620, 110, 1.4);
         drawCloud(ctx, 1150, 60, 1);
         drawCloud(ctx, 1850, 90, 1.2);
         drawCloud(ctx, 2400, 70, 1);
         drawBush(ctx, 480, groundY, 1.3);
         drawBush(ctx, 1300, groundY, 1);
         drawBush(ctx, 2100, groundY, 1.5);

         // flag pole + castle
         drawFlag(ctx, flagX, groundY, borgoColor);
         drawCastle(ctx, levelW - TILE * 2.2, groundY);

         // blocks
         for (const b of blocks) {
            const by = b.y - (b.bump || 0);
            if (b.kind === 'ground') drawGround(ctx, b.x, by);
            else if (b.kind === 'brick') drawBrick(ctx, b.x, by);
            else if (b.kind === 'question') drawQ(ctx, b.x, by, !!b.used, now);
            else if (b.kind === 'pipe') drawPipe(ctx, b.x, by);
         }

         // coins
         for (const c of coins) {
            if (c.got) continue;
            drawCoin(ctx, c.x, c.y, c.t);
         }

         // goombas
         for (const g of goombas) {
            if (!g.alive && g.dead <= 0) continue;
            drawGoomba(ctx, g.x, g.y, g.w, g.h, !g.alive, now);
         }

         // player
         drawMario(ctx, p.x, p.y, p.face, borgoColor, p.onGround, p.walkT, p.dead);

         ctx.restore();

         // HUD (screen-fixed)
         drawHUD(ctx, selectedBorgo!, coinCount, score, Math.max(0, Math.ceil(time)), lives);

         raf = requestAnimationFrame(step);
      };

      raf = requestAnimationFrame(step);
      return () => cancelAnimationFrame(raf);
      // eslint-disable-next-line react-hooks/exhaustive-deps
   }, [selectedBorgo, borgoColor, runKey, status]);

   // keyboard
   useEffect(() => {
      const blocked = ['ArrowLeft', 'ArrowRight', 'ArrowUp', 'ArrowDown', ' '];
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
      width: 76,
      height: 64,
      display: 'flex',
      alignItems: 'center',
      justifyContent: 'center',
      borderRadius: 2,
      bgcolor: borgoColor,
      color: '#fff',
      fontSize: 26,
      fontWeight: 700,
      cursor: 'pointer',
      boxShadow: 3,
      '&:active': {filter: 'brightness(0.85)'},
   };

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
                        Super Borgo Bros! Corri, salta sui Goomba e raggiungi la bandiera.
                        Tastiera: ← → muovi, ↑ / Spazio salta, Shift corri.
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
                        <Typography variant="h6" sx={noSelect}>
                           {selectedBorgo} — 🪙 {hud.coins} · {hud.score} pt · ⏱ {hud.time} · ❤ {hud.lives}
                        </Typography>
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
                           width={VIEW_W}
                           height={VIEW_H}
                           draggable={false}
                           style={{
                              width: '100%',
                              maxWidth: VIEW_W,
                              height: 'auto',
                              borderRadius: 8,
                              imageRendering: 'pixelated',
                              display: 'block',
                              touchAction: 'none',
                              userSelect: 'none',
                              WebkitUserSelect: 'none',
                           }}
                        />
                        {(status === 'dead' || status === 'gameover' || status === 'clear') && (
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
                                 gap: 2,
                              }}
                           >
                              <Typography variant="h4" sx={noSelect}>
                                 {status === 'clear'
                                    ? '🏁 Hai vinto!'
                                    : status === 'gameover'
                                       ? 'Game Over'
                                       : 'Ahia!'}
                              </Typography>
                              <Button
                                 variant="contained"
                                 onClick={
                                    status === 'dead'
                                       ? () => {
                                            setStatus('playing');
                                            setRunKey((kk) => kk + 1);
                                         }
                                       : restart
                                 }
                              >
                                 {status === 'dead' ? 'Riprova' : 'Gioca ancora'}
                              </Button>
                           </Box>
                        )}
                     </Box>

                     <Box
                        sx={{
                           ...noSelect,
                           mt: 2,
                           display: 'flex',
                           justifyContent: 'space-between',
                           alignItems: 'center',
                           gap: 2,
                        }}
                     >
                        <Box sx={{display: 'flex', gap: 1.5}}>
                           <Box sx={padSx} {...hold('ArrowLeft')}>
                              ◀
                           </Box>
                           <Box sx={padSx} {...hold('ArrowRight')}>
                              ▶
                           </Box>
                        </Box>
                        <Box sx={{display: 'flex', gap: 1.5}}>
                           <Box sx={{...padSx, fontSize: 16}} {...hold('Shift')}>
                              CORRI
                           </Box>
                           <Box sx={{...padSx, width: 96}} {...hold(' ')}>
                              SALTA
                           </Box>
                        </Box>
                     </Box>
                  </CardContent>
               </Card>
            )}
         </Box>
      </Container>
   );
};

// ---------------- pixel-art drawing helpers ----------------

function px(ctx: CanvasRenderingContext2D, x: number, y: number, w: number, h: number, c: string) {
   ctx.fillStyle = c;
   ctx.fillRect(Math.round(x), Math.round(y), Math.ceil(w), Math.ceil(h));
}

function drawGround(ctx: CanvasRenderingContext2D, x: number, y: number) {
   px(ctx, x, y, TILE, TILE, GROUND);
   px(ctx, x, y, TILE, 5, GROUND_TOP);
   px(ctx, x, y + TILE - 4, TILE, 4, GROUND_DARK);
   ctx.fillStyle = GROUND_DARK;
   ctx.fillRect(x + TILE / 2 - 1, y + 6, 2, TILE - 10);
   ctx.fillRect(x, y + TILE / 2 - 1, TILE, 2);
}

function drawBrick(ctx: CanvasRenderingContext2D, x: number, y: number) {
   px(ctx, x, y, TILE, TILE, BRICK);
   px(ctx, x, y, TILE, 3, '#F0A060');
   ctx.strokeStyle = BRICK_LINE;
   ctx.lineWidth = 2;
   ctx.strokeRect(x + 1, y + 1, TILE - 2, TILE - 2);
   ctx.beginPath();
   ctx.moveTo(x, y + TILE / 2);
   ctx.lineTo(x + TILE, y + TILE / 2);
   ctx.moveTo(x + TILE / 2, y);
   ctx.lineTo(x + TILE / 2, y + TILE / 2);
   ctx.moveTo(x + TILE / 4, y + TILE / 2);
   ctx.lineTo(x + TILE / 4, y + TILE);
   ctx.moveTo(x + (TILE * 3) / 4, y + TILE / 2);
   ctx.lineTo(x + (TILE * 3) / 4, y + TILE);
   ctx.stroke();
}

function drawQ(ctx: CanvasRenderingContext2D, x: number, y: number, used: boolean, t: number) {
   const base = used ? QBLOCK_USED : QBLOCK;
   const pulse = used ? 0 : Math.sin(t / 180) * 18;
   px(ctx, x, y, TILE, TILE, base);
   px(ctx, x, y, TILE, 4, `rgba(255,255,255,${used ? 0.15 : 0.5})`);
   px(ctx, x, y + TILE - 4, TILE, 4, QBLOCK_DARK);
   ctx.strokeStyle = '#000';
   ctx.lineWidth = 2;
   ctx.strokeRect(x + 1, y + 1, TILE - 2, TILE - 2);
   // rivets
   const rv = '#000';
   [
      [x + 4, y + 4],
      [x + TILE - 7, y + 4],
      [x + 4, y + TILE - 7],
      [x + TILE - 7, y + TILE - 7],
   ].forEach(([rx, ry]) => px(ctx, rx, ry, 3, 3, rv));
   if (!used) {
      ctx.fillStyle = `rgb(${255},${255},${Math.round(180 + pulse)})`;
      ctx.font = 'bold 20px monospace';
      ctx.textAlign = 'center';
      ctx.textBaseline = 'middle';
      ctx.fillText('?', x + TILE / 2, y + TILE / 2 + 1);
   }
}

function drawPipe(ctx: CanvasRenderingContext2D, x: number, y: number) {
   px(ctx, x, y, TILE, TILE, PIPE);
   px(ctx, x + 3, y, 6, TILE, PIPE_LIGHT);
   px(ctx, x + TILE - 6, y, 4, TILE, PIPE_DARK);
   px(ctx, x, y, TILE, 3, PIPE_DARK);
}

function drawCoin(ctx: CanvasRenderingContext2D, cx: number, cy: number, t: number) {
   const sw = Math.abs(Math.cos(t)) * 9 + 3;
   ctx.fillStyle = COIN;
   ctx.beginPath();
   ctx.ellipse(cx, cy, sw, 13, 0, 0, Math.PI * 2);
   ctx.fill();
   ctx.fillStyle = COIN_DARK;
   ctx.fillRect(cx - 1.5, cy - 7, 3, 14);
}

function drawGoomba(
   ctx: CanvasRenderingContext2D, x: number, y: number, w: number, h: number, dead: boolean, t: number,
) {
   if (dead) {
      px(ctx, x, y + h - 8, w, 8, GOOMBA);
      px(ctx, x + 4, y + h - 6, 4, 3, '#fff');
      px(ctx, x + w - 8, y + h - 6, 4, 3, '#fff');
      return;
   }
   const swap = Math.floor(t / 160) % 2 === 0;
   // body
   ctx.fillStyle = GOOMBA;
   ctx.beginPath();
   ctx.ellipse(x + w / 2, y + h / 2, w / 2, h / 2, 0, 0, Math.PI * 2);
   ctx.fill();
   px(ctx, x + 2, y + 3, w - 4, 4, '#C87830');
   // eyes
   px(ctx, x + 5, y + 9, 5, 6, '#fff');
   px(ctx, x + w - 10, y + 9, 5, 6, '#fff');
   px(ctx, x + (swap ? 7 : 6), y + 11, 2, 3, '#000');
   px(ctx, x + w - (swap ? 8 : 9), y + 11, 2, 3, '#000');
   // brows
   ctx.strokeStyle = '#000';
   ctx.lineWidth = 2;
   ctx.beginPath();
   ctx.moveTo(x + 4, y + 7);
   ctx.lineTo(x + 11, y + 11);
   ctx.moveTo(x + w - 4, y + 7);
   ctx.lineTo(x + w - 11, y + 11);
   ctx.stroke();
   // feet
   px(ctx, x + (swap ? 1 : 3), y + h - 5, 9, 5, GOOMBA_FOOT);
   px(ctx, x + w - (swap ? 10 : 12), y + h - 5, 9, 5, GOOMBA_FOOT);
}

function drawMario(
   ctx: CanvasRenderingContext2D,
   x: number, y: number, face: number, color: string,
   onGround: boolean, walkT: number, dead: boolean,
) {
   const f = face >= 0 ? 1 : -1;
   ctx.save();
   ctx.translate(Math.round(x + P_W / 2), Math.round(y));
   ctx.scale(f, 1);
   ctx.translate(-P_W / 2, 0);

   if (dead) {
      px(ctx, 4, 4, 16, 6, color);
      px(ctx, 3, 10, 18, 8, SKIN);
      px(ctx, 6, 18, 12, 10, color);
      ctx.restore();
      return;
   }

   const airborne = !onGround;
   const stride = Math.sin(walkT) ;
   // cap
   px(ctx, 4, 0, 16, 6, color);
   px(ctx, 2, 4, 6, 3, color);
   // face
   px(ctx, 5, 6, 15, 9, SKIN);
   // hair / sideburn
   px(ctx, 4, 8, 3, 6, '#7C2C00');
   // eye
   px(ctx, 14, 8, 3, 4, '#000');
   // mustache
   px(ctx, 12, 12, 8, 3, '#7C2C00');
   // shirt + overalls
   px(ctx, 3, 15, 18, 9, color);
   px(ctx, 7, 17, 10, 13, OVERALLS);
   px(ctx, 6, 17, 2, 9, OVERALLS); // strap
   px(ctx, 16, 17, 2, 9, OVERALLS);
   // button
   px(ctx, 11, 21, 2, 2, '#FAC000');

   // arms
   if (airborne) {
      px(ctx, 1, 15, 4, 7, SKIN);
      px(ctx, 19, 13, 4, 7, SKIN);
   } else {
      px(ctx, 2, 17, 4, 7, SKIN);
      px(ctx, 18, 17, 4, 7, SKIN);
   }

   // legs / shoes
   if (airborne) {
      px(ctx, 6, 26, 6, 5, OVERALLS);
      px(ctx, 13, 24, 6, 5, OVERALLS);
      px(ctx, 5, 28, 8, 3, SHOE);
      px(ctx, 14, 26, 8, 3, SHOE);
   } else {
      const a = stride * 4;
      px(ctx, 7 - a, 26, 6, 4, OVERALLS);
      px(ctx, 12 + a, 26, 6, 4, OVERALLS);
      px(ctx, 5 - a, 29, 9, 3, SHOE);
      px(ctx, 12 + a, 29, 9, 3, SHOE);
   }

   ctx.restore();
}

function drawCloud(ctx: CanvasRenderingContext2D, x: number, y: number, s: number) {
   ctx.fillStyle = CLOUD;
   const r = 16 * s;
   [[0, 0], [r, -r * 0.4], [r * 2, 0], [r * 0.6, r * 0.3], [r * 1.5, r * 0.3]].forEach(([dx, dy]) => {
      ctx.beginPath();
      ctx.arc(x + dx, y + dy, r, 0, Math.PI * 2);
      ctx.fill();
   });
   ctx.fillRect(x - r * 0.5, y, r * 3, r);
}

function drawHill(ctx: CanvasRenderingContext2D, x: number, groundY: number, s: number) {
   const w = 130 * s;
   const h = 70 * s;
   ctx.fillStyle = HILL;
   ctx.beginPath();
   ctx.moveTo(x - w / 2, groundY);
   ctx.quadraticCurveTo(x, groundY - h * 1.6, x + w / 2, groundY);
   ctx.fill();
   ctx.fillStyle = HILL_DARK;
   [[-w * 0.12, -h * 0.7], [w * 0.1, -h * 0.5]].forEach(([dx, dy]) => {
      ctx.beginPath();
      ctx.ellipse(x + dx, groundY + dy, 6 * s, 9 * s, 0, 0, Math.PI * 2);
      ctx.fill();
   });
}

function drawBush(ctx: CanvasRenderingContext2D, x: number, groundY: number, s: number) {
   ctx.fillStyle = HILL;
   const r = 18 * s;
   [[0, 0], [r * 1.1, -r * 0.3], [r * 2.2, 0]].forEach(([dx, dy]) => {
      ctx.beginPath();
      ctx.arc(x + dx, groundY - 4 + dy, r, 0, Math.PI * 2);
      ctx.fill();
   });
   ctx.fillRect(x - r * 0.6, groundY - r, r * 3.4, r);
}

function drawFlag(ctx: CanvasRenderingContext2D, x: number, groundY: number, color: string) {
   const top = groundY - TILE * 9;
   px(ctx, x + TILE / 2 - 2, top, 4, TILE * 9, '#0A8030');
   ctx.fillStyle = '#7CFC00';
   ctx.beginPath();
   ctx.arc(x + TILE / 2, top, 7, 0, Math.PI * 2);
   ctx.fill();
   ctx.fillStyle = color;
   ctx.beginPath();
   ctx.moveTo(x + TILE / 2 + 2, top + 12);
   ctx.lineTo(x + TILE / 2 + 2 + 34, top + 24);
   ctx.lineTo(x + TILE / 2 + 2, top + 36);
   ctx.closePath();
   ctx.fill();
}

function drawCastle(ctx: CanvasRenderingContext2D, x: number, groundY: number) {
   const w = TILE * 5;
   const h = TILE * 5;
   px(ctx, x, groundY - h, w, h, BRICK);
   for (let i = 0; i < 5; i++) px(ctx, x + i * (w / 5), groundY - h - 12, w / 5 - 6, 12, i % 2 ? BRICK : 'transparent');
   px(ctx, x + w / 2 - 14, groundY - 40, 28, 40, '#000');
   px(ctx, x + w / 2 - 5, groundY - h - 44, 10, 32, '#fff');
}

function drawHUD(
   ctx: CanvasRenderingContext2D, borgo: string, coins: number, score: number, time: number, lives: number,
) {
   ctx.fillStyle = 'rgba(0,0,0,0.35)';
   ctx.fillRect(0, 0, VIEW_W, 34);
   ctx.fillStyle = '#fff';
   ctx.font = 'bold 16px monospace';
   ctx.textAlign = 'left';
   ctx.textBaseline = 'middle';
   ctx.fillText(borgo.toUpperCase(), 12, 18);
   ctx.textAlign = 'center';
   ctx.fillText(`🪙×${String(coins).padStart(2, '0')}`, VIEW_W * 0.5 - 70, 18);
   ctx.fillText(`${String(score).padStart(6, '0')}`, VIEW_W * 0.5 + 30, 18);
   ctx.textAlign = 'right';
   ctx.fillText(`♥${lives}  TIME ${time}`, VIEW_W - 12, 18);
}

export default ArcadeGamePage;
