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

/* "Ripeti la Sequenza" (Simon): watch the sequence, repeat it. It grows
   by one each round. The score is the number of sequences reproduced
   correctly; the mini-podium keeps a borgo's best (max). */

const PADS = [
   {on: '#66bb6a', off: '#1b5e20'},
   {on: '#ef5350', off: '#b71c1c'},
   {on: '#ffee58', off: '#f9a825'},
   {on: '#42a5f5', off: '#0d47a1'},
   {on: '#bdbdbd', off: '#121212'},
];
const HI_KEY = 'sequenzaBest';
const FLASH_MS = 420;
const GAP_MS = 180;

type Phase = 'idle' | 'showing' | 'input' | 'over';

const SequenceGamePage: React.FC = () => {
   const [palioData, setPalioData] = useState<PalioData | null>(null);
   const [loading, setLoading] = useState(true);
   const [error, setError] = useState<string | null>(null);
   const [selectedBorgo, setSelectedBorgo] = useState<string | null>(null);
   const [runKey, setRunKey] = useState(0);
   const {selectedYear} = useYear();

   const [phase, setPhase] = useState<Phase>('idle');
   const [active, setActive] = useState<number | null>(null);
   const [score, setScore] = useState(0);
   const [best, setBest] = useState(0);

   const seqRef = useRef<number[]>([]);
   const inputIdxRef = useRef(0);
   const levelRef = useRef(0);
   const timersRef = useRef<ReturnType<typeof setTimeout>[]>([]);

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
      setBest(Number.isFinite(raw) ? raw : 0);
   }, []);

   const borgoColor: string = (selectedBorgo
      ? (palioData?.villages_colors as Record<string, string> | undefined)?.[selectedBorgo]
      : undefined) ?? '#7e57c2';

   const clearTimers = () => {
      timersRef.current.forEach(clearTimeout);
      timersRef.current = [];
   };
   useEffect(() => () => clearTimers(), []);

   const playback = useCallback((seq: number[]) => {
      clearTimers();
      setPhase('showing');
      setActive(null);
      let t = 500;
      seq.forEach((pad) => {
         timersRef.current.push(setTimeout(() => setActive(pad), t));
         timersRef.current.push(setTimeout(() => setActive(null), t + FLASH_MS));
         t += FLASH_MS + GAP_MS;
      });
      timersRef.current.push(
         setTimeout(() => {
            inputIdxRef.current = 0;
            setPhase('input');
         }, t),
      );
   }, []);

   const nextRound = useCallback(() => {
      // A brand-new random sequence each round (not the previous one with
      // one tap appended) — you can't coast on memorising a prefix.
      levelRef.current += 1;
      seqRef.current = Array.from({length: levelRef.current}, () =>
         Math.floor(Math.random() * PADS.length),
      );
      playback(seqRef.current);
   }, [playback]);

   const beginRun = useCallback(() => {
      clearTimers();
      seqRef.current = [];
      inputIdxRef.current = 0;
      levelRef.current = 0;
      setScore(0);
      setRunKey((k) => k + 1);
      nextRound();
   }, [nextRound]);

   const startWithBorgo = (borgo: string) => {
      setSelectedBorgo(borgo);
      beginRun();
   };

   // Submit once when the run ends, with the reached score.
   const submittedRun = useRef(-1);
   const endGame = useCallback(
      (finalScore: number) => {
         setPhase('over');
         setBest((b) => {
            if (finalScore > b) {
               try {
                  window.localStorage.setItem(HI_KEY, String(finalScore));
               } catch {
                  /* ignore quota / privacy mode */
               }
               return finalScore;
            }
            return b;
         });
         if (selectedBorgo && submittedRun.current !== runKey) {
            submittedRun.current = runKey;
            submitMiniGameScore({game: 'sequenza', borgo: selectedBorgo, score: finalScore});
         }
      },
      [selectedBorgo, runKey],
   );

   const flashPad = (pad: number) => {
      setActive(pad);
      timersRef.current.push(setTimeout(() => setActive(null), 180));
   };

   const handlePad = (pad: number) => {
      if (phase !== 'input') return;
      flashPad(pad);
      const seq = seqRef.current;
      if (pad !== seq[inputIdxRef.current]) {
         endGame(score);
         return;
      }
      inputIdxRef.current += 1;
      if (inputIdxRef.current === seq.length) {
         const reached = seq.length;
         setScore(reached);
         setPhase('showing');
         timersRef.current.push(setTimeout(() => nextRound(), 650));
      }
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
   const banner =
      phase === 'showing'
         ? 'Guarda la sequenza…'
         : phase === 'input'
            ? 'Ripeti!'
            : phase === 'over'
               ? 'Sbagliato!'
               : '';

   return (
      <Container maxWidth="lg">
         <Box sx={{mt: 4, mb: 4}}>
            <Box sx={{mb: 3}}>
               <Button component={RouterLink} to=".." size="small" sx={{minWidth: 0, pl: 0, mb: 0.5}}>
                  ← Mini-giochi
               </Button>
               <Typography variant="h4" component="h1">
                  Ripeti la Sequenza
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
                              🏆 record {best} · sequenza {score}
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

                     <Typography
                        variant="h6"
                        align="center"
                        sx={{mb: 1.5, color: phase === 'over' ? 'error.main' : borgoColor, minHeight: 32}}
                     >
                        {banner}
                     </Typography>

                     <Box
                        sx={{
                           position: 'relative',
                           width: '100%',
                           maxWidth: 340,
                           aspectRatio: '1 / 1',
                           mx: 'auto',
                           userSelect: 'none',
                           touchAction: 'manipulation',
                        }}
                     >
                        {PADS.map((p, i) => {
                           // Equal-size pads on the 5 vertices of a pentagon
                           // (first one at the top, then clockwise).
                           const a = -Math.PI / 2 + i * ((2 * Math.PI) / PADS.length);
                           return (
                              <Box
                                 key={i}
                                 onPointerDown={(e) => {
                                    e.preventDefault();
                                    handlePad(i);
                                 }}
                                 sx={{
                                    position: 'absolute',
                                    width: '33%',
                                    aspectRatio: '1 / 1',
                                    left: `${50 + 32 * Math.cos(a)}%`,
                                    top: `${50 + 32 * Math.sin(a)}%`,
                                    transform: 'translate(-50%, -50%)',
                                    borderRadius: '50%',
                                    border: '1px solid rgba(255,255,255,0.12)',
                                    bgcolor: active === i ? p.on : p.off,
                                    boxShadow: active === i ? `0 0 26px ${p.on}` : 3,
                                    cursor: phase === 'input' ? 'pointer' : 'default',
                                    transition: 'background-color .08s, box-shadow .08s',
                                 }}
                              />
                           );
                        })}
                     </Box>

                     {phase === 'over' && (
                        <Box sx={{mt: 2.5, textAlign: 'center'}}>
                           <Typography variant="h6">
                              Sequenza raggiunta: {score}
                           </Typography>
                           <Button variant="contained" sx={{mt: 1}} onClick={beginRun}>
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

export default SequenceGamePage;
