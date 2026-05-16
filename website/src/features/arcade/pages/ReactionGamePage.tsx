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

/* "Tempo di Reazione": three consecutive rounds — wait for green, tap as
   fast as you can. The score rewards CONSISTENCY: it's the average of the
   3 reaction times. Tapping before green repeats the round (no cheating
   the average with a lucky early click).

   The mini-podium aggregates by max with higher = better, so we submit a
   derived speed score = round(100000 / avgMs): a 200 ms average → 500,
   a 350 ms average → 285. The human-readable record (best avg ms) lives
   in localStorage. */

const ROUNDS = 3;
const MIN_WAIT = 1200;
const MAX_WAIT = 3500;
const HI_KEY = 'reazioneBestMs';

type Phase = 'idle' | 'wait' | 'go' | 'tooSoon' | 'result';

const speedScore = (avgMs: number) => Math.max(1, Math.round(100000 / avgMs));

const ReactionGamePage: React.FC = () => {
   const [palioData, setPalioData] = useState<PalioData | null>(null);
   const [loading, setLoading] = useState(true);
   const [error, setError] = useState<string | null>(null);
   const [selectedBorgo, setSelectedBorgo] = useState<string | null>(null);
   const [status, setStatus] = useState<'play' | 'gameover'>('play');
   const [runKey, setRunKey] = useState(0);
   const {selectedYear} = useYear();

   const [phase, setPhase] = useState<Phase>('idle');
   const [times, setTimes] = useState<number[]>([]);
   const [bestMs, setBestMs] = useState<number | null>(null);

   const timerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
   const goAtRef = useRef(0);

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
      setBestMs(raw > 0 ? raw : null);
   }, []);

   const borgoColor: string = (selectedBorgo
      ? (palioData?.villages_colors as Record<string, string> | undefined)?.[selectedBorgo]
      : undefined) ?? '#1e88e5';

   const avgMs = times.length
      ? Math.round(times.reduce((a, b) => a + b, 0) / times.length)
      : 0;

   const clearTimer = () => {
      if (timerRef.current) {
         clearTimeout(timerRef.current);
         timerRef.current = null;
      }
   };

   const armRound = useCallback(() => {
      setPhase('wait');
      clearTimer();
      const delay = MIN_WAIT + Math.random() * (MAX_WAIT - MIN_WAIT);
      timerRef.current = setTimeout(() => {
         goAtRef.current = performance.now();
         setPhase('go');
      }, delay);
   }, []);

   const beginRun = useCallback(() => {
      setTimes([]);
      setStatus('play');
      setRunKey((k) => k + 1);
      armRound();
   }, [armRound]);

   const startWithBorgo = (borgo: string) => {
      setSelectedBorgo(borgo);
      beginRun();
   };

   useEffect(() => () => clearTimer(), []);

   // Submit the finished run once. Higher derived score = faster average.
   const submittedRun = useRef(-1);
   useEffect(() => {
      if (
         status === 'gameover' &&
         selectedBorgo &&
         times.length === ROUNDS &&
         submittedRun.current !== runKey
      ) {
         submittedRun.current = runKey;
         submitMiniGameScore({
            game: 'reazione',
            borgo: selectedBorgo,
            score: speedScore(avgMs),
         });
      }
   }, [status, runKey, selectedBorgo, times.length, avgMs]);

   const tap = useCallback(() => {
      if (phase === 'wait') {
         clearTimer();
         setPhase('tooSoon');
         return;
      }
      if (phase === 'tooSoon') {
         armRound();
         return;
      }
      if (phase === 'go') {
         const dt = Math.round(performance.now() - goAtRef.current);
         setTimes((prev) => {
            const next = [...prev, dt];
            if (next.length >= ROUNDS) {
               const a = Math.round(next.reduce((x, y) => x + y, 0) / next.length);
               setPhase('result');
               setStatus('gameover');
               setBestMs((b) => {
                  if (b == null || a < b) {
                     try {
                        window.localStorage.setItem(HI_KEY, String(a));
                     } catch {
                        /* ignore quota / privacy mode */
                     }
                     return a;
                  }
                  return b;
               });
            } else {
               armRound();
            }
            return next;
         });
      }
   }, [phase, armRound]);

   useEffect(() => {
      const onKey = (e: KeyboardEvent) => {
         if (e.key === ' ' || e.key === 'ArrowUp') {
            e.preventDefault();
            tap();
         }
      };
      window.addEventListener('keydown', onKey);
      return () => window.removeEventListener('keydown', onKey);
   }, [tap]);

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

   const arena = {
      idle: {bg: '#37474f', main: '—', sub: ''},
      wait: {bg: '#c62828', main: 'Aspetta il verde…', sub: `Turno ${times.length + 1} / ${ROUNDS}`},
      go: {bg: '#2e7d32', main: 'TOCCA!', sub: 'Adesso!'},
      tooSoon: {bg: '#ef6c00', main: 'Troppo presto!', sub: 'Tocca per ripetere il turno'},
      result: {bg: borgoColor, main: `${avgMs} ms`, sub: 'media dei 3 turni'},
   }[phase];

   return (
      <Container maxWidth="lg">
         <Box sx={{mt: 4, mb: 4}}>
            <Box sx={{mb: 3}}>
               <Button component={RouterLink} to=".." size="small" sx={{minWidth: 0, pl: 0, mb: 0.5}}>
                  ← Mini-giochi
               </Button>
               <Typography variant="h4" component="h1">
                  Tempo di Reazione
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
                              🏆 record {bestMs != null ? `${bestMs} ms` : '—'}
                           </Typography>
                        </Box>
                        <Box sx={{display: 'flex', gap: 1}}>
                           <Button variant="outlined" size="small" onClick={beginRun}>
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
                           if (status !== 'gameover') tap();
                        }}
                        sx={{
                           userSelect: 'none',
                           touchAction: 'none',
                           cursor: status === 'gameover' ? 'default' : 'pointer',
                           height: {xs: 280, sm: 340},
                           borderRadius: 2,
                           bgcolor: arena.bg,
                           color: '#fff',
                           display: 'flex',
                           flexDirection: 'column',
                           alignItems: 'center',
                           justifyContent: 'center',
                           gap: 1,
                           transition: 'background-color .12s',
                           textAlign: 'center',
                           px: 2,
                        }}
                     >
                        <Typography variant="h3" sx={{fontWeight: 800}}>
                           {arena.main}
                        </Typography>
                        {arena.sub && (
                           <Typography variant="body1" sx={{opacity: 0.9}}>
                              {arena.sub}
                           </Typography>
                        )}
                     </Box>

                     <Box sx={{mt: 2, display: 'flex', gap: 1, justifyContent: 'center', flexWrap: 'wrap'}}>
                        {Array.from({length: ROUNDS}).map((_, i) => (
                           <Box
                              key={i}
                              sx={{
                                 px: 1.5,
                                 py: 0.5,
                                 borderRadius: 1,
                                 border: '1px solid',
                                 borderColor: 'divider',
                                 fontSize: 14,
                                 fontWeight: 600,
                                 minWidth: 78,
                                 textAlign: 'center',
                                 color: times[i] != null ? 'text.primary' : 'text.secondary',
                              }}
                           >
                              {times[i] != null ? `${times[i]} ms` : `T${i + 1}`}
                           </Box>
                        ))}
                     </Box>

                     {status === 'gameover' && (
                        <Box sx={{mt: 2, textAlign: 'center'}}>
                           <Typography variant="h6">
                              Media: {avgMs} ms
                           </Typography>
                           <Typography variant="body2" color="text.secondary" sx={{mb: 1.5}}>
                              Più sei costante, meglio è.
                           </Typography>
                           <Button variant="contained" onClick={beginRun}>
                              Riprova
                           </Button>
                        </Box>
                     )}
                  </CardContent>
               </Card>
            )}
         </Box>
      </Container>
   );
};

export default ReactionGamePage;
