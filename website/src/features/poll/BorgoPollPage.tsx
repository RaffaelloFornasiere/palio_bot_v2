import React, { useCallback, useEffect, useState } from 'react';
import {
  Container,
  Box,
  Typography,
  Button,
  CircularProgress,
  Alert,
  Card,
  CardContent,
} from '@mui/material';
import { FavoriteRounded as HeartIcon } from '@mui/icons-material';
import { getClientId } from '../../utils/clientId';
import { getPollStats, getPollStatus, PollStats, PollStatus } from '../../utils/pollApi';
import { usePalioVillages } from './usePalioVillages';
import PollResults from './PollResults';
import BorgoPollDialog from './BorgoPollDialog';

/* Public stats page + entry point to vote. Linked from the nav as
   "Borgo più amato". Current year only — the poll is always live. */

const BorgoPollPage: React.FC = () => {
  const { villages, colors } = usePalioVillages();
  const [stats, setStats] = useState<PollStats | null>(null);
  const [status, setStatus] = useState<PollStatus | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [dialogOpen, setDialogOpen] = useState(false);

  const refresh = useCallback(async () => {
    try {
      const [s, st] = await Promise.all([
        getPollStats(),
        getPollStatus(getClientId()),
      ]);
      setStats(s);
      setStatus(st);
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Errore nel caricamento');
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    refresh();
  }, [refresh]);

  const votedToday = !!status?.voted_today;

  return (
    <Container maxWidth="sm">
      <Box sx={{ mt: 4, mb: 4 }}>
        <Box sx={{ display: 'flex', alignItems: 'center', gap: 1.5, mb: 1 }}>
          <HeartIcon sx={{ color: 'secondary.main' }} />
          <Typography variant="h4" component="h1">
            Il borgo più amato
          </Typography>
        </Box>
        <Box sx={{ mb: 3 }} />

        {loading ? (
          <Box sx={{ display: 'flex', justifyContent: 'center', py: 6 }}>
            <CircularProgress />
          </Box>
        ) : error ? (
          <Alert severity="error">{error}</Alert>
        ) : (
          <Card>
            <CardContent sx={{ display: 'flex', flexDirection: 'column', gap: 2.5 }}>
              {stats && stats.total_votes > 0 ? (
                <PollResults stats={stats} villages={villages} colors={colors} />
              ) : (
                <Typography variant="body2" color="text.secondary" sx={{ py: 2 }}>
                  Ancora nessun voto. Sii il primo a scegliere il borgo migliore!
                </Typography>
              )}

              <Box>
                <Button
                  fullWidth
                  variant="contained"
                  disabled={votedToday}
                  onClick={() => setDialogOpen(true)}
                >
                  {votedToday ? 'Hai già votato oggi' : 'Vota il borgo di oggi'}
                </Button>
                {votedToday && (
                  <Typography
                    variant="caption"
                    color="text.secondary"
                    sx={{ display: 'block', textAlign: 'center', mt: 1 }}
                  >
                    Torna domani per votare di nuovo.
                  </Typography>
                )}
              </Box>
            </CardContent>
          </Card>
        )}
      </Box>

      <BorgoPollDialog
        open={dialogOpen}
        onClose={() => setDialogOpen(false)}
        votedToday={votedToday}
        onVoted={refresh}
      />
    </Container>
  );
};

export default BorgoPollPage;
