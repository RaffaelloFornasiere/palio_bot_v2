import React, { useCallback, useEffect, useState } from 'react';
import {
  Dialog,
  DialogTitle,
  DialogContent,
  DialogActions,
  Button,
  Box,
  Typography,
  ButtonBase,
  CircularProgress,
  Alert,
} from '@mui/material';
import { alpha } from '@mui/material/styles';
import { useNavigate } from 'react-router-dom';
import VillageToken from '../../components/VillageToken';
import { curatedVillageColor } from '../../utils/colorUtils';
import { getClientId } from '../../utils/clientId';
import { castVote, getPollStats, PollStats } from '../../utils/pollApi';
import { usePalioVillages } from './usePalioVillages';
import PollResults from './PollResults';
import Turnstile from './Turnstile';

const SITEKEY = process.env.REACT_APP_TURNSTILE_SITEKEY;

interface Props {
  open: boolean;
  onClose: () => void;
  /** True if this device already voted for the current festival-day. */
  votedToday?: boolean;
  /** Called after a vote is accepted, so the parent can refresh status. */
  onVoted?: () => void;
}

type Phase = 'choose' | 'submitting' | 'done';

const BorgoPollDialog: React.FC<Props> = ({ open, onClose, votedToday, onVoted }) => {
  const navigate = useNavigate();
  const { villages, colors, loading } = usePalioVillages();
  const [selected, setSelected] = useState<string | null>(null);
  const [token, setToken] = useState<string | null>(null);
  const [phase, setPhase] = useState<Phase>('choose');
  const [stats, setStats] = useState<PollStats | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [alreadyVoted, setAlreadyVoted] = useState<boolean>(!!votedToday);

  // Already voted today → skip straight to results.
  useEffect(() => {
    if (!open) return;
    if (votedToday) {
      setAlreadyVoted(true);
      getPollStats()
        .then((s) => {
          setStats(s);
          setPhase('done');
        })
        .catch(() => setPhase('choose'));
    }
  }, [open, votedToday]);

  // Reset transient state whenever the dialog is reopened.
  useEffect(() => {
    if (open && !votedToday) {
      setSelected(null);
      setToken(null);
      setPhase('choose');
      setStats(null);
      setError(null);
      setAlreadyVoted(false);
    }
  }, [open, votedToday]);

  const handleToken = useCallback((t: string | null) => setToken(t), []);

  const submit = async () => {
    if (!selected) return;
    setPhase('submitting');
    setError(null);
    try {
      const res = await castVote({
        clientId: getClientId(),
        borgo: selected,
        turnstileToken: token,
      });
      setStats(res.stats);
      setAlreadyVoted(res.status === 'already_voted');
      setPhase('done');
      onVoted?.();
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Errore imprevisto');
      setPhase('choose');
      setToken(null); // Turnstile token is single-use; force a fresh one.
    }
  };

  const tokenRequired = !!SITEKEY;
  const canSubmit = !!selected && (!tokenRequired || !!token) && phase === 'choose';

  return (
    <Dialog open={open} onClose={onClose} maxWidth="xs" fullWidth>
      {phase === 'done' ? (
        <>
          <DialogTitle sx={{ pb: 0.5 }}>
            {alreadyVoted ? 'Hai già votato oggi' : 'Grazie per il tuo voto!'}
          </DialogTitle>
          <DialogContent>
            <Typography variant="body2" color="text.secondary" sx={{ mb: 2 }}>
              {alreadyVoted
                ? 'Potrai votare di nuovo domani. Ecco la classifica attuale:'
                : 'Ecco come sta andando la sfida tra i borghi:'}
            </Typography>
            {stats && (
              <PollResults stats={stats} villages={villages} colors={colors} compact />
            )}
          </DialogContent>
          <DialogActions sx={{ px: 3, pb: 2 }}>
            <Button onClick={onClose}>Chiudi</Button>
            <Button
              variant="contained"
              onClick={() => {
                onClose();
                navigate('/borgo-amato');
              }}
            >
              Classifica completa
            </Button>
          </DialogActions>
        </>
      ) : (
        <>
          <DialogTitle sx={{ pb: 0.5 }}>Qual è il borgo migliore?</DialogTitle>
          <DialogContent>
            <Typography variant="body2" color="text.secondary" sx={{ mb: 2 }}>
              Vota il tuo borgo del cuore. Un voto al giorno.
            </Typography>

            {loading ? (
              <Box sx={{ display: 'flex', justifyContent: 'center', py: 3 }}>
                <CircularProgress size={28} />
              </Box>
            ) : (
              <Box
                sx={{
                  display: 'grid',
                  gridTemplateColumns: '1fr 1fr',
                  gap: 1,
                }}
              >
                {villages.map((v) => {
                  const accent = curatedVillageColor(colors[v] || '#888888');
                  const isSel = selected === v;
                  return (
                    <ButtonBase
                      key={v}
                      onClick={() => setSelected(v)}
                      sx={{
                        justifyContent: 'flex-start',
                        gap: 1,
                        p: 1.25,
                        borderRadius: 2,
                        border: '1px solid',
                        borderColor: isSel ? accent : 'divider',
                        bgcolor: isSel ? alpha(accent, 0.16) : 'transparent',
                        transition: 'all .15s ease',
                      }}
                    >
                      <VillageToken village={v} rawColor={colors[v]} size={28} />
                      <Typography variant="body2" fontWeight={isSel ? 700 : 500} noWrap>
                        {v}
                      </Typography>
                    </ButtonBase>
                  );
                })}
              </Box>
            )}

            {error && (
              <Alert severity="error" sx={{ mt: 2 }}>
                {error}
              </Alert>
            )}

            <Box sx={{ mt: 2 }}>
              <Turnstile onToken={handleToken} />
            </Box>
          </DialogContent>
          <DialogActions sx={{ px: 3, pb: 2 }}>
            <Button onClick={onClose} color="inherit">
              Più tardi
            </Button>
            <Button
              variant="contained"
              onClick={submit}
              disabled={!canSubmit}
              startIcon={
                phase === 'submitting' ? <CircularProgress size={16} /> : undefined
              }
            >
              Vota
            </Button>
          </DialogActions>
        </>
      )}
    </Dialog>
  );
};

export default BorgoPollDialog;
