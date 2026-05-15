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
const MUSH_CAP = '#E03030';

const TILE = 32;
const VIEW_W = TILE * 17; // 544
const VIEW_H = TILE * 14; // 448

// Physics modelled on the documented SMB engine: asymmetric gravity
// (low while rising with jump held, high when falling / button released
// -> that IS the variable-height jump), jump strength scaled by run
// speed, plus the standard coyote-time + jump-buffer for tight feel.
const GRAVITY_JUMP = 1250; // while ascending and jump held
const GRAVITY_FALL = 2600; // falling, or jump released mid-rise
const WALK_ACCEL = 1150;
const RUN_MAX = 380;
const WALK_MAX = 230;
const FRICTION = 1600;
const JUMP_V = -560; // standstill jump impulse
const JUMP_SPEED_BONUS = 130; // extra impulse at full run speed
const COYOTE = 0.09;
const JUMP_BUFFER = 0.12;
const MAX_FALL = 900;
const GOOMBA_SPEED = 55;
const START_TIME = 300;

const P_W = 24;
const P_H_SMALL = 30;
const P_H_BIG = 46;

const TILES_W = 116;
const GROUND_ROW = 12; // rows 12 & 13 are ground
const GROUND_Y = GROUND_ROW * TILE; // 384 (top surface of the ground)
const CLUSTER_ROW = 9; // y=288, ~3 tiles above ground -> always jump-reachable
const LEVEL_W = TILES_W * TILE;

type Solid = {x: number; y: number; w: number; h: number};
interface Block extends Solid {
   kind: 'ground' | 'brick' | 'question' | 'pipe';
   gives?: 'coin' | 'mushroom';
   used?: boolean;
   broken?: boolean;
   bump?: number;
}
interface Coin {x: number; y: number; t: number; got?: boolean}
interface Goomba {x: number; y: number; vx: number; vy: number; w: number; h: number; dead: number; alive: boolean}
interface Mushroom {x: number; y: number; vx: number; vy: number; w: number; h: number; active: boolean; emerge: number}

const ri = (a: number, b: number) => Math.floor(a + Math.random() * (b - a + 1));

// Max empty-column run the player can clear. Small Mario's standstill
// jump arc (apex ~125px / airtime ~0.76s) covers ~5 tiles even at walk
// speed and ~9 at run speed; 4 keeps a safe margin for imperfect timing.
const MAX_GAP = 4;

// One constructive attempt: a single-height ground "spine" with pits
// isolated by guaranteed run-up + landing, low jump-over pipes never
// next to a pit, and bonus clusters/coins/mushrooms that sit ABOVE a
// fully-solid stretch so they can never block the path.
function generateOnce() {
   const solid: boolean[] = new Array(TILES_W).fill(true);
   let c = 10; // 0..9 always solid (safe start / run-up)
   while (c < TILES_W - 22) {
      c += ri(5, 10); // flat run = breathing room / run-up
      if (c >= TILES_W - 22) break;
      if (Math.random() < 0.55) {
         const gap = ri(2, MAX_GAP - 1); // 2..3, strictly below the cap
         for (let i = 0; i < gap; i++) solid[c + i] = false;
         c += gap + ri(4, 7); // guaranteed landing + run-up after the pit
      }
   }

   let blocks: Block[] = [];
   for (let col = 0; col < TILES_W; col++) {
      if (solid[col]) {
         blocks.push({x: col * TILE, y: GROUND_Y, w: TILE, h: TILE, kind: 'ground'});
         blocks.push({x: col * TILE, y: GROUND_Y + TILE, w: TILE, h: TILE, kind: 'ground'});
      }
   }
   const spanSolid = (a: number, b: number) => {
      for (let col = a; col < b; col++) if (!solid[col]) return false;
      return true;
   };

   // pipes: only with solid ground for a few tiles around -> always
   // jump-over-able and never adjacent to a pit
   const pipeCols: number[] = [];
   for (let attempt = 0; attempt < ri(2, 4); attempt++) {
      const col = ri(18, TILES_W - 26);
      if (!spanSolid(col - 2, col + 3)) continue;
      if (pipeCols.some((pc) => Math.abs(pc - col) < 7)) continue;
      const h = ri(2, 3);
      for (let k = 1; k <= h; k++) {
         blocks.push({x: col * TILE, y: GROUND_Y - k * TILE, w: TILE, h: TILE, kind: 'pipe'});
      }
      pipeCols.push(col);
   }
   const isPipeCol = (col: number) => pipeCols.includes(col);

   // bonus clusters at a jump-reachable row, only over fully-solid
   // ground (3-tile clearance underneath -> never a wall)
   const questions: Block[] = [];
   for (let attempt = 0; attempt < ri(3, 5); attempt++) {
      const len = ri(3, 6);
      const start = ri(16, TILES_W - 26);
      if (!spanSolid(start - 1, start + len + 1)) continue;
      let blocked = false;
      for (let i = 0; i < len; i++) if (isPipeCol(start + i)) blocked = true;
      if (blocked) continue;
      let hasQ = false;
      const made: Block[] = [];
      for (let i = 0; i < len; i++) {
         const isQ = Math.random() < 0.45;
         if (isQ) hasQ = true;
         made.push({
            x: (start + i) * TILE, y: CLUSTER_ROW * TILE, w: TILE, h: TILE,
            kind: isQ ? 'question' : 'brick',
            gives: isQ ? 'coin' : undefined,
         });
      }
      if (!hasQ) {
         const mid = made[Math.floor(len / 2)];
         mid.kind = 'question';
         mid.gives = 'coin';
      }
      made.forEach((b) => {
         blocks.push(b);
         if (b.kind === 'question') questions.push(b);
      });
   }
   // guarantee at least one ? exists, then always >=1 mushroom dispenser
   // (purely a bonus; bricks are platforms, never required to finish)
   if (questions.length === 0) {
      const b: Block = {x: 16 * TILE, y: CLUSTER_ROW * TILE, w: TILE, h: TILE, kind: 'question', gives: 'coin'};
      blocks.push(b);
      questions.push(b);
   }
   const nMush = Math.max(1, Math.min(questions.length, ri(1, 2)));
   for (let i = 0; i < nMush; i++) questions[ri(0, questions.length - 1)].gives = 'mushroom';

   const coins: Coin[] = [];
   const overlapsBlock = (cx: number, cy: number) =>
      blocks.some((b) => cx > b.x - 12 && cx < b.x + b.w + 12 && cy > b.y - 16 && cy < b.y + b.h + 16);
   for (let i = 0; i < ri(16, 24); i++) {
      for (let t = 0; t < 8; t++) {
         const col = ri(11, TILES_W - 16);
         if (!solid[col] || isPipeCol(col)) continue;
         const cy = GROUND_Y - TILE * ri(1, 3) + 6;
         const cx = col * TILE + TILE / 2;
         if (overlapsBlock(cx, cy)) continue;
         coins.push({x: cx, y: cy, t: Math.random() * 6});
         break;
      }
   }

   const goombas: Goomba[] = [];
   for (let i = 0; i < ri(4, 7); i++) {
      for (let t = 0; t < 8; t++) {
         const col = ri(16, TILES_W - 20);
         if (!solid[col] || isPipeCol(col)) continue;
         goombas.push({
            x: col * TILE, y: GROUND_Y - 26,
            vx: Math.random() < 0.5 ? -GOOMBA_SPEED : GOOMBA_SPEED,
            vy: 0, w: 26, h: 26, dead: 0, alive: true,
         });
         break;
      }
   }

   for (let s = 0; s < 4; s++) {
      const col = TILES_W - 15 + s;
      for (let k = 1; k <= s + 1; k++) {
         blocks.push({x: col * TILE, y: GROUND_Y - k * TILE, w: TILE, h: TILE, kind: 'ground'});
      }
   }
   const flagCol = TILES_W - 7;
   return {blocks, coins, goombas, flagX: flagCol * TILE, solid, flagCol};
}

// Sound under-approximation: with single-height ground, the level is
// beatable iff every empty run before the flag is within one jump and
// the flag stands on solid ground. If this passes the level is truly
// completable (it may reject some beatable ones -> we just regenerate).
function isBeatable(solid: boolean[], flagCol: number) {
   let run = 0;
   for (let c = 0; c < flagCol; c++) {
      if (solid[c]) run = 0;
      else if (++run > MAX_GAP) return false;
   }
   return solid[flagCol];
}

function buildLevel() {
   for (let attempt = 0; attempt < 24; attempt++) {
      const lvl = generateOnce();
      if (isBeatable(lvl.solid, lvl.flagCol)) return lvl;
   }
   // deterministic safe fallback (flat ground + one mushroom + flag)
   const blocks: Block[] = [];
   for (let col = 0; col < TILES_W; col++) {
      blocks.push({x: col * TILE, y: GROUND_Y, w: TILE, h: TILE, kind: 'ground'});
      blocks.push({x: col * TILE, y: GROUND_Y + TILE, w: TILE, h: TILE, kind: 'ground'});
   }
   blocks.push({x: 30 * TILE, y: CLUSTER_ROW * TILE, w: TILE, h: TILE, kind: 'question', gives: 'mushroom'});
   return {
      blocks, coins: [] as Coin[], goombas: [] as Goomba[],
      flagX: (TILES_W - 7) * TILE, solid: new Array(TILES_W).fill(true), flagCol: TILES_W - 7,
   };
}

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

      let {blocks, coins, goombas, flagX} = buildLevel();
      const mushrooms: Mushroom[] = [];

      const p = {
         x: TILE * 2, y: GROUND_Y - P_H_SMALL, vx: 0, vy: 0,
         onGround: false, face: 1, walkT: 0, big: false, invuln: 0,
         coyote: 0, jumpBuf: 0, prevJump: false,
         dead: false, deadT: 0, win: false, winT: 0,
      };
      const ph = () => (p.big ? P_H_BIG : P_H_SMALL);

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

         if (p.win) {
            p.winT += dt;
            if (p.y + ph() < GROUND_Y) p.y += 180 * dt;
            else p.x += 90 * dt;
            if (p.winT > 2.4) {
               setHud({coins: coinCount, score, lives, time: Math.ceil(time)});
               setStatus('clear');
               return;
            }
         } else if (p.dead) {
            p.deadT += dt;
            p.vy = Math.min(p.vy + GRAVITY_FALL * dt, MAX_FALL);
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
            if (p.invuln > 0) p.invuln -= dt;

            timeAcc += dt;
            if (timeAcc >= 1) {
               timeAcc -= 1;
               time -= 1;
               if (time <= 0) die();
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

            // coyote time + jump buffering (standard platformer feel)
            p.coyote = p.onGround ? COYOTE : Math.max(0, p.coyote - dt);
            const jumpPressed = jumpHeld && !p.prevJump;
            p.jumpBuf = jumpPressed ? JUMP_BUFFER : Math.max(0, p.jumpBuf - dt);
            p.prevJump = jumpHeld;
            if (p.jumpBuf > 0 && p.coyote > 0) {
               p.vy = JUMP_V - (Math.abs(p.vx) / RUN_MAX) * JUMP_SPEED_BONUS;
               p.onGround = false;
               p.coyote = 0;
               p.jumpBuf = 0;
            }
            // asymmetric gravity = authentic SMB variable-height jump:
            // gentle while rising with jump held, heavy otherwise.
            const gravNow = p.vy < 0 && jumpHeld ? GRAVITY_JUMP : GRAVITY_FALL;
            p.vy = Math.min(p.vy + gravNow * dt, MAX_FALL);

            const H = ph();

            // horizontal
            p.x += p.vx * dt;
            // SMB one-way camera: a solid wall at the visible left edge
            // (cameraX only ever increases) so you can't walk off-screen.
            const leftWall = cameraX;
            if (p.x < leftWall) {
               p.x = leftWall;
               if (p.vx < 0) p.vx = 0;
            }
            for (const b of blocks) {
               if (aabb(p.x, p.y, P_W, H, b)) {
                  if (p.vx > 0) p.x = b.x - P_W;
                  else if (p.vx < 0) p.x = b.x + b.w;
                  p.vx = 0;
               }
            }

            // vertical
            p.y += p.vy * dt;
            p.onGround = false;
            for (const b of blocks) {
               if (aabb(p.x, p.y, P_W, H, b)) {
                  if (p.vy > 0) {
                     p.y = b.y - H;
                     p.vy = 0;
                     p.onGround = true;
                  } else if (p.vy < 0) {
                     p.y = b.y + b.h;
                     p.vy = 0;
                     if (b.kind === 'question' && !b.used) {
                        b.used = true;
                        b.bump = 8;
                        if (b.gives === 'mushroom') {
                           mushrooms.push({
                              x: b.x, y: b.y, vx: 70, vy: 0, w: 24, h: 24,
                              active: true, emerge: TILE,
                           });
                           score += 100;
                        } else {
                           coinCount += 1;
                           score += 200;
                           if (coinCount >= 100) coinCount = 0;
                        }
                     } else if (b.kind === 'brick') {
                        if (p.big) {
                           b.broken = true;
                           score += 50;
                        } else {
                           b.bump = 6;
                        }
                     } else if (b.kind === 'ground') {
                        b.bump = 4;
                     }
                  }
               }
            }
            if (blocks.some((b) => b.broken)) blocks = blocks.filter((b) => !b.broken);
            blocks.forEach((b) => {
               if (b.bump && b.bump > 0) b.bump = Math.max(0, b.bump - 60 * dt);
            });

            if (Math.abs(p.vx) > 10 && p.onGround) p.walkT += dt * Math.abs(p.vx) * 0.04;
            else p.walkT = 0;

            if (p.y > VIEW_H + 80) die();

            if (!p.win && p.x + P_W > flagX && p.x < flagX + TILE) {
               p.win = true;
               p.vx = 0;
               p.vy = 0;
               score += Math.ceil(time) * 10;
               p.x = flagX - 2;
            }

            // goombas
            for (const g of goombas) {
               if (!g.alive) {
                  if (g.dead > 0) g.dead -= dt;
                  continue;
               }
               g.vy = Math.min(g.vy + GRAVITY_FALL * dt, MAX_FALL);
               g.x += g.vx * dt;
               for (const b of blocks) {
                  if (aabb(g.x, g.y, g.w, g.h, b) && b.y < g.y + g.h - 4) {
                     if (g.vx > 0) g.x = b.x - g.w;
                     else g.x = b.x + b.w;
                     g.vx = -g.vx;
                  }
               }
               g.y += g.vy * dt;
               for (const b of blocks) {
                  if (aabb(g.x, g.y, g.w, g.h, b) && g.vy > 0) {
                     g.y = b.y - g.h;
                     g.vy = 0;
                  }
               }
               if (g.y > VIEW_H + 80) g.alive = false;

               if (!p.dead && !p.win && aabb(p.x, p.y, P_W, H, g)) {
                  const stomp = p.vy > 0 && p.y + H - g.y < 18;
                  if (stomp) {
                     g.alive = false;
                     g.dead = 0.5;
                     p.vy = -420;
                     score += 100;
                  } else if (p.invuln <= 0) {
                     if (p.big) {
                        p.big = false;
                        p.y += P_H_BIG - P_H_SMALL;
                        p.invuln = 2;
                     } else {
                        die();
                     }
                  }
               }
            }

            // coins
            for (const co of coins) {
               if (co.got) continue;
               co.t += dt * 6;
               if (aabb(p.x, p.y, P_W, H, {x: co.x - 10, y: co.y - 14, w: 20, h: 28})) {
                  co.got = true;
                  coinCount += 1;
                  score += 200;
                  if (coinCount >= 100) coinCount = 0;
               }
            }

            // mushrooms
            for (const m of mushrooms) {
               if (!m.active) continue;
               if (m.emerge > 0) {
                  const rise = 64 * dt;
                  m.y -= rise;
                  m.emerge -= rise;
               } else {
                  m.vy = Math.min(m.vy + GRAVITY_FALL * dt, MAX_FALL);
                  m.x += m.vx * dt;
                  for (const b of blocks) {
                     if (aabb(m.x, m.y, m.w, m.h, b) && b.y < m.y + m.h - 4) {
                        if (m.vx > 0) m.x = b.x - m.w;
                        else m.x = b.x + b.w;
                        m.vx = -m.vx;
                     }
                  }
                  m.y += m.vy * dt;
                  for (const b of blocks) {
                     if (aabb(m.x, m.y, m.w, m.h, b) && m.vy > 0) {
                        m.y = b.y - m.h;
                        m.vy = 0;
                     }
                  }
                  if (m.y > VIEW_H + 80) m.active = false;
                  if (m.active && aabb(p.x, p.y, P_W, H, m)) {
                     m.active = false;
                     score += 1000;
                     if (!p.big) {
                        p.big = true;
                        p.y -= P_H_BIG - P_H_SMALL;
                     }
                  }
               }
            }
         }

         const target = p.x - VIEW_W * 0.38;
         cameraX = Math.max(0, Math.min(LEVEL_W - VIEW_W, Math.max(cameraX, target)));

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

         for (let i = 0; i < 6; i++) {
            drawHill(ctx, 200 + i * 620 + (i % 2) * 140, GROUND_Y, i % 2 ? 1 : 1.4);
            drawCloud(ctx, 260 + i * 560, 60 + (i % 3) * 26, 1 + (i % 2) * 0.3);
            drawBush(ctx, 470 + i * 540, GROUND_Y, 1 + (i % 2) * 0.4);
         }

         drawFlag(ctx, flagX, GROUND_Y, borgoColor);
         drawCastle(ctx, LEVEL_W - TILE * 3, GROUND_Y);

         for (const b of blocks) {
            const by = b.y - (b.bump || 0);
            if (b.kind === 'ground') drawGround(ctx, b.x, by);
            else if (b.kind === 'brick') drawBrick(ctx, b.x, by);
            else if (b.kind === 'question') drawQ(ctx, b.x, by, !!b.used, now);
            else if (b.kind === 'pipe') drawPipe(ctx, b.x, by);
         }

         for (const co of coins) {
            if (co.got) continue;
            drawCoin(ctx, co.x, co.y, co.t);
         }
         for (const m of mushrooms) {
            if (!m.active) continue;
            drawMushroom(ctx, m.x, m.y, m.w, m.h);
         }
         for (const g of goombas) {
            if (!g.alive && g.dead <= 0) continue;
            drawGoomba(ctx, g.x, g.y, g.w, g.h, !g.alive, now);
         }

         const blink = p.invuln > 0 && Math.floor(now / 90) % 2 === 0;
         if (!blink) drawMario(ctx, p.x, p.y, P_W, ph(), p.face, borgoColor, p.onGround, p.walkT, p.dead, p.big);

         ctx.restore();
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
      width: {xs: 46, sm: 58},
      height: {xs: 42, sm: 50},
      display: 'flex',
      alignItems: 'center',
      justifyContent: 'center',
      borderRadius: 2,
      bgcolor: borgoColor,
      color: '#fff',
      fontSize: {xs: 18, sm: 22},
      fontWeight: 700,
      cursor: 'pointer',
      boxShadow: 2,
      '&:active': {filter: 'brightness(0.85)'},
   };

   return (
      <Container maxWidth="lg">
         <Box sx={{mt: 4, mb: 4}}>
            <Box sx={{display: 'flex', justifyContent: 'space-between', alignItems: 'center', mb: 3}}>
               <Box sx={{display: 'flex', alignItems: 'baseline', gap: 1.5}}>
                  <Button component={RouterLink} to=".." size="small" sx={{minWidth: 0}}>
                     ← Mini-giochi
                  </Button>
                  <Typography variant="h4" component="h1">
                     Super Borgo Bros
                  </Typography>
               </Box>
            </Box>

            {!selectedBorgo ? (
               <Card>
                  <CardContent>
                     <Typography variant="h6" gutterBottom>
                        Scegli il tuo borgo
                     </Typography>
                     <Typography variant="body2" color="text.secondary" sx={{mb: 3}}>
                        Super Borgo Bros! Corri, salta sui Goomba, prendi i funghi per
                        diventare grande e raggiungi la bandiera. Ogni partita è diversa.
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
                           flexWrap: 'wrap',
                           gap: 1,
                        }}
                     >
                        <Box sx={{display: 'flex', gap: 1}}>
                           <Box sx={padSx} {...hold('ArrowLeft')}>
                              ◀
                           </Box>
                           <Box sx={padSx} {...hold('ArrowRight')}>
                              ▶
                           </Box>
                        </Box>
                        <Box sx={{display: 'flex', gap: 1}}>
                           <Box sx={{...padSx, fontSize: {xs: 11, sm: 13}}} {...hold('Shift')}>
                              CORRI
                           </Box>
                           <Box sx={{...padSx, width: {xs: 64, sm: 78}}} {...hold(' ')}>
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
   [
      [x + 4, y + 4],
      [x + TILE - 7, y + 4],
      [x + 4, y + TILE - 7],
      [x + TILE - 7, y + TILE - 7],
   ].forEach(([rx, ry]) => px(ctx, rx, ry, 3, 3, '#000'));
   if (!used) {
      ctx.fillStyle = `rgb(255,255,${Math.round(180 + pulse)})`;
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

function drawMushroom(ctx: CanvasRenderingContext2D, x: number, y: number, w: number, h: number) {
   // cap
   ctx.fillStyle = MUSH_CAP;
   ctx.beginPath();
   ctx.arc(x + w / 2, y + h * 0.45, w / 2, Math.PI, 0);
   ctx.fill();
   px(ctx, x, y + h * 0.42, w, h * 0.13, MUSH_CAP);
   // white spots
   ctx.fillStyle = '#fff';
   ctx.beginPath();
   ctx.arc(x + w * 0.28, y + h * 0.38, 3, 0, Math.PI * 2);
   ctx.arc(x + w * 0.72, y + h * 0.38, 3, 0, Math.PI * 2);
   ctx.arc(x + w * 0.5, y + h * 0.22, 3.5, 0, Math.PI * 2);
   ctx.fill();
   // stalk + eyes
   px(ctx, x + w * 0.2, y + h * 0.55, w * 0.6, h * 0.45, SKIN);
   px(ctx, x + w * 0.34, y + h * 0.66, 3, 5, '#000');
   px(ctx, x + w * 0.56, y + h * 0.66, 3, 5, '#000');
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
   ctx.fillStyle = GOOMBA;
   ctx.beginPath();
   ctx.ellipse(x + w / 2, y + h / 2, w / 2, h / 2, 0, 0, Math.PI * 2);
   ctx.fill();
   px(ctx, x + 2, y + 3, w - 4, 4, '#C87830');
   px(ctx, x + 5, y + 9, 5, 6, '#fff');
   px(ctx, x + w - 10, y + 9, 5, 6, '#fff');
   px(ctx, x + (swap ? 7 : 6), y + 11, 2, 3, '#000');
   px(ctx, x + w - (swap ? 8 : 9), y + 11, 2, 3, '#000');
   ctx.strokeStyle = '#000';
   ctx.lineWidth = 2;
   ctx.beginPath();
   ctx.moveTo(x + 4, y + 7);
   ctx.lineTo(x + 11, y + 11);
   ctx.moveTo(x + w - 4, y + 7);
   ctx.lineTo(x + w - 11, y + 11);
   ctx.stroke();
   px(ctx, x + (swap ? 1 : 3), y + h - 5, 9, 5, GOOMBA_FOOT);
   px(ctx, x + w - (swap ? 10 : 12), y + h - 5, 9, 5, GOOMBA_FOOT);
}

function drawMario(
   ctx: CanvasRenderingContext2D,
   x: number, y: number, w: number, h: number, face: number, color: string,
   onGround: boolean, walkT: number, dead: boolean, big: boolean,
) {
   ctx.save();
   ctx.translate(Math.round(x + w / 2), Math.round(y));
   ctx.scale(face >= 0 ? 1 : -1, 1);
   ctx.translate(-12, 0);
   ctx.scale(w / 24, h / 32); // sprite authored in a 24x32 box

   if (dead) {
      px(ctx, 4, 4, 16, 6, color);
      px(ctx, 3, 10, 18, 8, SKIN);
      px(ctx, 6, 18, 12, 10, color);
      ctx.restore();
      return;
   }

   const airborne = !onGround;
   const stride = Math.sin(walkT);
   const torso = big ? '#FFFFFF' : color; // big Mario gets a white shirt under coloured cap

   px(ctx, 4, 0, 16, 6, color);
   px(ctx, 2, 4, 6, 3, color);
   px(ctx, 5, 6, 15, 9, SKIN);
   px(ctx, 4, 8, 3, 6, '#7C2C00');
   px(ctx, 14, 8, 3, 4, '#000');
   px(ctx, 12, 12, 8, 3, '#7C2C00');
   px(ctx, 3, 15, 18, 9, torso);
   px(ctx, 7, 17, 10, 13, OVERALLS);
   px(ctx, 6, 17, 2, 9, OVERALLS);
   px(ctx, 16, 17, 2, 9, OVERALLS);
   px(ctx, 11, 21, 2, 2, '#FAC000');

   if (airborne) {
      px(ctx, 1, 15, 4, 7, SKIN);
      px(ctx, 19, 13, 4, 7, SKIN);
   } else {
      px(ctx, 2, 17, 4, 7, SKIN);
      px(ctx, 18, 17, 4, 7, SKIN);
   }

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
   const hh = 70 * s;
   ctx.fillStyle = HILL;
   ctx.beginPath();
   ctx.moveTo(x - w / 2, groundY);
   ctx.quadraticCurveTo(x, groundY - hh * 1.6, x + w / 2, groundY);
   ctx.fill();
   ctx.fillStyle = HILL_DARK;
   [[-w * 0.12, -hh * 0.7], [w * 0.1, -hh * 0.5]].forEach(([dx, dy]) => {
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
   for (let i = 0; i < 5; i++) {
      if (i % 2) px(ctx, x + i * (w / 5), groundY - h - 12, w / 5 - 6, 12, BRICK);
   }
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
