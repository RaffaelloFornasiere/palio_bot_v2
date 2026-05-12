import React, { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import {
  Alert, Box, Button, Chip, IconButton, Stack, Table, TableBody, TableCell,
  TableHead, TableRow, Typography,
} from '@mui/material';
import EditIcon from '@mui/icons-material/Edit';
import CloseIcon from '@mui/icons-material/Close';
import ChevronRightIcon from '@mui/icons-material/ChevronRight';
import { JsonForm } from '../components/JsonForm';
import { palioLeaderboardHint } from '../schema';
import { useLeaderboardContext } from './EditLeaderboardPage';

const LeaderboardOverviewView: React.FC = () => {
  const { content, setContent, villages } = useLeaderboardContext();
  const navigate = useNavigate();
  const [editingPalio, setEditingPalio] = useState(false);

  const palio = content.palio_leaderboard ?? {};
  const games = content.game_leaderboards ?? {};
  const gameIds = Object.keys(games);

  // For the read-only view, order villages by position; fallback to villages
  // order, then any extras.
  const orderedPalio = Object.entries(palio)
    .sort(([, a], [, b]) => (a?.position ?? 99) - (b?.position ?? 99));

  return (
    <Box>
      <Stack direction="row" alignItems="center" justifyContent="space-between" sx={{ mb: 1 }}>
        <Typography variant="h6">Classifica Palio</Typography>
        <Button
          size="small"
          startIcon={editingPalio ? <CloseIcon /> : <EditIcon />}
          onClick={() => setEditingPalio((v) => !v)}
        >
          {editingPalio ? 'Chiudi' : 'Modifica'}
        </Button>
      </Stack>

      {editingPalio && (
        <Alert severity="warning" sx={{ mb: 2 }}>
          La classifica Palio viene ricalcolata automaticamente da Stato giochi
          (somma dei punti per gioco). Qualsiasi modifica successiva allo
          stato dei giochi sovrascriverà queste correzioni manuali.
        </Alert>
      )}

      {editingPalio ? (
        <JsonForm
          value={palio}
          onChange={(nv) => setContent((prev) => ({ ...prev, palio_leaderboard: nv }))}
          hint={palioLeaderboardHint}
          villages={villages}
        />
      ) : (
        <Table size="small" sx={{ mb: 3 }}>
          <TableHead>
            <TableRow>
              <TableCell sx={{ pl: 0, width: 40 }}>#</TableCell>
              <TableCell>Borgo</TableCell>
              <TableCell align="right" sx={{ pr: 0 }}>Punti</TableCell>
            </TableRow>
          </TableHead>
          <TableBody>
            {orderedPalio.length === 0 && (
              <TableRow>
                <TableCell colSpan={3} sx={{ color: 'text.secondary', pl: 0 }}>
                  Nessun punteggio ancora.
                </TableCell>
              </TableRow>
            )}
            {orderedPalio.map(([village, entry]) => (
              <TableRow key={village}>
                <TableCell sx={{ pl: 0 }}>{entry?.position ?? '-'}</TableCell>
                <TableCell>
                  <Chip label={village} size="small" color="primary" />
                </TableCell>
                <TableCell align="right" sx={{ pr: 0 }}>{entry?.points ?? 0}</TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
      )}

      <Typography variant="h6" sx={{ mt: 4, mb: 1 }}>Classifiche per gioco</Typography>
      <Typography variant="body2" color="text.secondary" sx={{ mb: 1 }}>
        Clicca un gioco per modificarne la classifica.
      </Typography>
      <Table size="small">
        <TableHead>
          <TableRow>
            <TableCell sx={{ pl: 0 }}>Nome</TableCell>
            <TableCell>Divisioni</TableCell>
            <TableCell sx={{ width: 40, pr: 0 }} />
          </TableRow>
        </TableHead>
        <TableBody>
          {gameIds.length === 0 && (
            <TableRow>
              <TableCell colSpan={3} sx={{ color: 'text.secondary', pl: 0 }}>
                Nessuna classifica per gioco. Si popola completando giochi in
                Stato giochi.
              </TableCell>
            </TableRow>
          )}
          {gameIds.map((id) => {
            const g = games[id];
            const divs = g.divisions ?? [];
            return (
              <TableRow
                key={id}
                hover
                onClick={() => navigate(id)}
                sx={{ cursor: 'pointer' }}
              >
                <TableCell sx={{ pl: 0 }}>{g.game_name || '(senza nome)'}</TableCell>
                <TableCell>
                  {divs.length === 0
                    ? '—'
                    : divs.map((d) => d.name).join(', ')}
                </TableCell>
                <TableCell sx={{ pr: 0 }}>
                  <IconButton size="small" aria-label="apri">
                    <ChevronRightIcon fontSize="small" />
                  </IconButton>
                </TableCell>
              </TableRow>
            );
          })}
        </TableBody>
      </Table>
    </Box>
  );
};

export default LeaderboardOverviewView;
