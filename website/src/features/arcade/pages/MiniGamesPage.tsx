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
} from '@mui/material';
import {alpha} from '@mui/material/styles';
import VillageToken from '../../../components/VillageToken';
import {usePalioVillages} from '../../poll/usePalioVillages';
import {getMiniGamePodium, MiniGamePodium} from '../../../utils/minigameApi';

const GAMES = [
   {
      to: 'bros',
      emoji: '🍄',
      title: 'Super Borgo Bros',
      desc: 'Platformer alla Super Mario: corri, salta sui Goomba, prendi i funghi e raggiungi la bandiera.',
   },
   {
      to: 'dino',
      emoji: '🦖',
      title: 'Borgo Dino',
      desc: 'Endless runner alla Chrome Dino: salta i cactus, schiva i pterodattili, batti il record.',
   },
];

const MEDALS = ['🥇', '🥈', '🥉'];

const MiniGamesPage: React.FC = () => {
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

   return (
      <Container maxWidth="lg">
         <Box sx={{mt: 4, mb: 4}}>
            <Box sx={{mb: 3}}>
               <Typography variant="h4" component="h1">
                  Mini-giochi
               </Typography>
            </Box>

            <Box
               sx={{
                  display: 'grid',
                  gap: 2,
                  gridTemplateColumns: {xs: '1fr', sm: '1fr 1fr'},
               }}
            >
               {GAMES.map((g) => (
                  <Card key={g.to}>
                     <CardActionArea component={RouterLink} to={g.to} sx={{height: '100%'}}>
                        <CardContent>
                           <Typography variant="h2" sx={{lineHeight: 1, mb: 1}}>
                              {g.emoji}
                           </Typography>
                           <Typography variant="h6" gutterBottom>
                              {g.title}
                           </Typography>
                           <Typography variant="body2" color="text.secondary">
                              {g.desc}
                           </Typography>
                        </CardContent>
                     </CardActionArea>
                  </Card>
               ))}
            </Box>

            <Card sx={{mt: 3}}>
               <CardContent>
                  <Typography variant="h6" gutterBottom>
                     🏆 Mini-podio
                  </Typography>
                  <Typography variant="body2" color="text.secondary" sx={{mb: 2}}>
                     Classifica goliardica dei mini-giochi. Per ogni gioco i borghi
                     prendono 10 · 7 · 5 · 3 · 1 punti (come nei giochi ufficiali);
                     qui sotto la somma. Solo per divertimento — <b>non</b> conta per
                     la classifica ufficiale del Palio.
                  </Typography>

                  {loading ? (
                     <Box sx={{display: 'flex', justifyContent: 'center', py: 3}}>
                        <CircularProgress size={28} />
                     </Box>
                  ) : !hasScores ? (
                     <Typography variant="body2" color="text.secondary">
                        Nessun punteggio ancora — gioca per primo e porta il tuo borgo
                        in cima!
                     </Typography>
                  ) : (
                     <>
                        <Box sx={{display: 'flex', flexDirection: 'column', gap: 1.25}}>
                           {overall.map((row, i) => (
                              <Box
                                 key={row.borgo}
                                 sx={{display: 'flex', alignItems: 'center', gap: 1.25}}
                              >
                                 <Box
                                    sx={{
                                       width: 26,
                                       textAlign: 'center',
                                       fontSize: 18,
                                       flexShrink: 0,
                                    }}
                                 >
                                    {MEDALS[i] ?? row.position}
                                 </Box>
                                 <VillageToken village={row.borgo} rawColor={colors[row.borgo]} size={32} />
                                 <Box sx={{flex: 1, minWidth: 0}}>
                                    <Typography variant="body2" fontWeight={700} noWrap>
                                       {row.borgo}
                                    </Typography>
                                    <Typography variant="caption" color="text.secondary">
                                       {Object.entries(row.by_game)
                                          .map(
                                             ([g, pts]) =>
                                                `${games[g]?.label ?? g}: ${pts}`,
                                          )
                                          .join(' · ') || '—'}
                                    </Typography>
                                 </Box>
                                 <Typography variant="subtitle1" fontWeight={800} sx={{flexShrink: 0}}>
                                    {row.points} pt
                                 </Typography>
                              </Box>
                           ))}
                        </Box>

                        <Divider sx={{my: 2}} />

                        <Box
                           sx={{
                              display: 'grid',
                              gap: 2,
                              gridTemplateColumns: {xs: '1fr', sm: '1fr 1fr'},
                           }}
                        >
                           {Object.entries(games).map(([gid, g]) => (
                              <Box key={gid}>
                                 <Typography variant="subtitle2" gutterBottom>
                                    {g.label}
                                 </Typography>
                                 {g.ranking.length === 0 ? (
                                    <Typography variant="caption" color="text.secondary">
                                       Ancora nessuna partita.
                                    </Typography>
                                 ) : (
                                    g.ranking.map((r) => (
                                       <Box
                                          key={r.borgo}
                                          sx={{
                                             display: 'flex',
                                             alignItems: 'center',
                                             gap: 1,
                                             py: 0.5,
                                             borderRadius: 1,
                                             px: 0.5,
                                             bgcolor:
                                                r.position === 1
                                                   ? alpha('#f4ecdd', 0.06)
                                                   : 'transparent',
                                          }}
                                       >
                                          <Box sx={{width: 18, fontSize: 13, color: 'text.secondary'}}>
                                             {r.position}
                                          </Box>
                                          <VillageToken
                                             village={r.borgo}
                                             rawColor={colors[r.borgo]}
                                             size={22}
                                          />
                                          <Typography variant="body2" sx={{flex: 1, minWidth: 0}} noWrap>
                                             {r.borgo}
                                          </Typography>
                                          <Typography variant="caption" color="text.secondary">
                                             {r.score} · {r.points} pt
                                          </Typography>
                                       </Box>
                                    ))
                                 )}
                              </Box>
                           ))}
                        </Box>
                     </>
                  )}
               </CardContent>
            </Card>
         </Box>
      </Container>
   );
};

export default MiniGamesPage;
