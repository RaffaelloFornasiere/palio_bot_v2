import React, {useEffect, useState} from 'react';
import {Link as RouterLink} from 'react-router-dom';
import {
   Container,
   Typography,
   Box,
   Card,
   CardActionArea,
   CardContent,
   Divider,
   CircularProgress,
   useTheme,
} from '@mui/material';
import {alpha} from '@mui/material/styles';
import {usePalioVillages} from '../../poll/usePalioVillages';
import {getMiniGamePodium, MiniGamePodium} from '../../../utils/minigameApi';
import {curatedVillageColor, hexToRgb} from '../../../utils/colorUtils';
import {MASCOTS, FALLBACK_EMOJI} from '../../../utils/villages';
import '../../leaderboard/components/MascotRace.css';

/* Mini-giochi hub. Same podium visual as the main Classifica
   (reuses MascotRace.css), just smaller and static — no race/animation.
   Each game's full ranking lives inside that game's card. Goliardic:
   does NOT count toward the official Palio leaderboard. */

const GAMES = [
   {
      to: 'bros',
      emoji: '🍄',
      title: 'Super Borgo Bros',
      rule: 'Somma dei punti di tutte le partite giocate.',
   },
   {
      to: 'dino',
      emoji: '🦖',
      title: 'Borgo Dino',
      rule: 'Conta solo il record (la partita migliore).',
   },
   {
      to: 'flappy',
      emoji: '🐤',
      title: 'Flappy Borgo',
      rule: 'Conta solo il record (la partita migliore).',
   },
   {
      to: 'reazione',
      emoji: '🔔',
      title: 'Tempo di Reazione',
      rule: 'Punteggio dalla media di 3 turni: più alto = più veloce.',
   },
   {
      to: 'sequenza',
      emoji: '🔁',
      title: 'Ripeti la Sequenza',
      rule: 'La sequenza più lunga ripetuta correttamente.',
   },
];

// Same podium geometry as MascotRace.
const HEIGHTS = [1.0, 0.76, 0.57, 0.4, 0.28];
const RANK_TO_SLOT = [2, 1, 3, 0, 4];
const SLOT_PLACE = [4, 2, 1, 3, 5];
const MEDALS = ['🥇', '🥈', '🥉', '4°', '5°'];

function textOn(hex: string): string {
   const rgb = hexToRgb(hex);
   if (!rgb) return '#fff';
   const l = (0.299 * rgb.r + 0.587 * rgb.g + 0.114 * rgb.b) / 255;
   return l > 0.6 ? '#000' : '#fff';
}

const MiniGamesPage: React.FC = () => {
   const theme = useTheme();
   const {colors} = usePalioVillages();
   const [podium, setPodium] = useState<MiniGamePodium | null>(null);
   const [loading, setLoading] = useState(true);

   useEffect(() => {
      let alive = true;
      getMiniGamePodium()
         .then((p) => alive && setPodium(p))
         .catch(() => alive && setPodium(null))
         .finally(() => alive && setLoading(false));
      return () => {
         alive = false;
      };
   }, []);

   const overall = podium?.overall ?? [];
   const games = podium?.games ?? {};
   const hasScores = overall.length > 0;

   const cssVars = {
      '--mr-line': theme.palette.divider,
      '--mr-panel': alpha(theme.palette.text.primary, 0.06),
      '--mr-muted': theme.palette.text.secondary,
      '--mr-accent': theme.palette.success.main,
      '--mr-grid-min': alpha(theme.palette.text.primary, 0.05),
      '--mr-grid-maj': alpha(theme.palette.text.primary, 0.13),
      // smaller than the main podium (--podH there is 150px)
      '--podH': '92px',
   } as React.CSSProperties;

   return (
      <Container maxWidth="lg">
         <Box sx={{mt: 4, mb: 4}}>
            <Box sx={{mb: 1}}>
               <Typography variant="h4" component="h1">
                  Mini-giochi
               </Typography>
            </Box>

            <Card variant="outlined" sx={{mb: 3}}>
               <CardContent sx={{pt: 1.5, px: 2, pb: 2, '&:last-child': {pb: 2}}}>
                  {loading ? (
                     <Box sx={{display: 'flex', justifyContent: 'center', py: 4}}>
                        <CircularProgress size={28} />
                     </Box>
                  ) : (
                     <>
                        <Box className="mascot-race" sx={cssVars}>
                           <div className="podium">
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
                              {overall.map((row, rank) => {
                                 const slot = RANK_TO_SLOT[rank] ?? rank;
                                 const color = curatedVillageColor(
                                    colors[row.borgo] || '#888888',
                                 );
                                 return (
                                    <div
                                       key={'ptok' + row.borgo}
                                       className="ptok"
                                       style={{
                                          left: `calc(${slot} * 20% + 10%)`,
                                          bottom: `calc(var(--podH) * ${
                                             HEIGHTS[rank] ?? 0.2
                                          } + 30px)`,
                                       }}
                                    >
                                       <span
                                          className="dot"
                                          style={{background: color, color: textOn(color)}}
                                       >
                                          {MASCOTS[row.borgo] || FALLBACK_EMOJI}
                                       </span>
                                       <span className="tp">{row.points}</span>
                                    </div>
                                 );
                              })}
                           </div>
                        </Box>
                        {!hasScores && (
                           <Typography
                              variant="body2"
                              color="text.secondary"
                              align="center"
                              sx={{mt: 1}}
                           >
                              Nessun punteggio ancora — gioca per primo e porta il tuo
                              borgo sul podio!
                           </Typography>
                        )}
                     </>
                  )}
               </CardContent>
            </Card>

            <Box
               sx={{
                  display: 'grid',
                  gap: 2,
                  gridTemplateColumns: {xs: '1fr', sm: '1fr 1fr'},
               }}
            >
               {GAMES.map((g) => {
                  const ranking = games[g.to]?.ranking ?? [];
                  return (
                     <Card key={g.to} sx={{display: 'flex', flexDirection: 'column'}}>
                        <CardActionArea component={RouterLink} to={g.to}>
                           <CardContent sx={{pb: 1}}>
                              <Typography variant="h2" sx={{lineHeight: 1, mb: 1}}>
                                 {g.emoji}
                              </Typography>
                              <Typography variant="h6">
                                 {g.title}
                              </Typography>
                           </CardContent>
                        </CardActionArea>
                        <Divider />
                        <CardContent sx={{flex: 1, pt: 1.5}}>
                           <Box
                              sx={{
                                 display: 'flex',
                                 justifyContent: 'space-between',
                                 alignItems: 'baseline',
                                 mb: 1,
                              }}
                           >
                              <Typography variant="subtitle2">Classifica</Typography>
                              <Typography variant="caption" color="text.secondary">
                                 {g.rule}
                              </Typography>
                           </Box>
                           {ranking.length === 0 ? (
                              <Typography variant="body2" color="text.secondary">
                                 Ancora nessuna partita.
                              </Typography>
                           ) : (
                              <Box sx={{display: 'flex', flexDirection: 'column', gap: 0.75}}>
                                 {ranking.map((r) => {
                                    const color = curatedVillageColor(
                                       colors[r.borgo] || '#888888',
                                    );
                                    return (
                                       <Box
                                          key={r.borgo}
                                          sx={{
                                             display: 'flex',
                                             alignItems: 'center',
                                             gap: 1,
                                             py: 0.25,
                                          }}
                                       >
                                          <Box
                                             sx={{
                                                width: 22,
                                                textAlign: 'center',
                                                fontSize: r.position <= 3 ? 16 : 13,
                                                color: 'text.secondary',
                                                flexShrink: 0,
                                             }}
                                          >
                                             {MEDALS[r.position - 1] ?? r.position}
                                          </Box>
                                          <Box
                                             sx={{
                                                width: 26,
                                                height: 26,
                                                borderRadius: '50%',
                                                display: 'grid',
                                                placeItems: 'center',
                                                fontSize: 15,
                                                background: color,
                                                color: textOn(color),
                                                flexShrink: 0,
                                             }}
                                          >
                                             {MASCOTS[r.borgo] || FALLBACK_EMOJI}
                                          </Box>
                                          <Typography
                                             variant="body2"
                                             fontWeight={600}
                                             sx={{flex: 1, minWidth: 0}}
                                             noWrap
                                          >
                                             {r.borgo}
                                          </Typography>
                                          <Typography
                                             variant="caption"
                                             color="text.secondary"
                                             sx={{flexShrink: 0}}
                                          >
                                             {r.score} · <b>{r.points} pt</b>
                                          </Typography>
                                       </Box>
                                    );
                                 })}
                              </Box>
                           )}
                        </CardContent>
                     </Card>
                  );
               })}
            </Box>
         </Box>
      </Container>
   );
};

export default MiniGamesPage;
