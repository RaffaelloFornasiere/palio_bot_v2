import React, { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import {
  Box, Table, TableHead, TableBody, TableRow, TableCell, Chip,
  IconButton, Typography, Button, Menu, MenuItem, Stack,
} from '@mui/material';
import AddIcon from '@mui/icons-material/Add';
import ChevronRightIcon from '@mui/icons-material/ChevronRight';
import { useGameStatusContext } from './EditGameStatusPage';

const STATUS_LABELS: Record<string, string> = {
  'not-started': 'Non iniziato',
  'in-progress': 'In corso',
  'completed': 'Completato',
};

const STATUS_COLORS: Record<string, 'default' | 'warning' | 'success'> = {
  'not-started': 'default',
  'in-progress': 'warning',
  'completed': 'success',
};

const GameStatusListView: React.FC = () => {
  const { content, setContent, games } = useGameStatusContext();
  const navigate = useNavigate();
  const [addAnchor, setAddAnchor] = useState<null | HTMLElement>(null);

  const scores = content.game_scores ?? {};
  const nameById = new Map(games.map((g) => [g.id, g.name]));
  // Stable sort: known games (in palio.json order) first, then any extras
  // present only in game_status, alphabetically.
  const known = games.map((g) => g.id).filter((id) => id in scores);
  const extras = Object.keys(scores).filter((id) => !nameById.has(id)).sort();
  const orderedIds = [...known, ...extras];

  // Games defined in palio.json but not yet tracked in game_scores.
  const missing = games.filter((g) => !(g.id in scores));

  const addGame = (id: string) => {
    setContent((prev) => ({
      ...prev,
      game_scores: {
        ...(prev.game_scores ?? {}),
        [id]: {
          status: 'not-started',
          applied_bonuses: [],
          applied_penalties: [],
        },
      },
    }));
    setAddAnchor(null);
    navigate(id);
  };

  return (
    <Box>
      <Stack direction="row" alignItems="center" justifyContent="space-between" sx={{ mb: 1 }}>
        <Typography variant="body2" color="text.secondary">
          Clicca un gioco per modificarlo. Le modifiche si salvano insieme.
        </Typography>
        <Button
          size="small"
          startIcon={<AddIcon />}
          onClick={(e) => setAddAnchor(e.currentTarget)}
          disabled={missing.length === 0}
        >
          Aggiungi
        </Button>
        <Menu
          anchorEl={addAnchor}
          open={addAnchor != null}
          onClose={() => setAddAnchor(null)}
        >
          {missing.map((g) => (
            <MenuItem key={g.id} onClick={() => addGame(g.id)}>
              {g.name}
            </MenuItem>
          ))}
        </Menu>
      </Stack>
      <Table size="small">
        <TableHead>
          <TableRow>
            <TableCell sx={{ pl: 0 }}>Nome</TableCell>
            <TableCell>Stato</TableCell>
            <TableCell sx={{ width: 40, pr: 0 }} />
          </TableRow>
        </TableHead>
        <TableBody>
          {orderedIds.map((id) => {
            const g = scores[id] ?? {};
            const status: string = g.status ?? 'not-started';
            return (
              <TableRow
                key={id}
                hover
                onClick={() => navigate(id)}
                sx={{ cursor: 'pointer' }}
              >
                <TableCell sx={{ pl: 0 }}>{nameById.get(id) ?? '(senza nome)'}</TableCell>
                <TableCell>
                  <Chip
                    label={STATUS_LABELS[status] ?? status}
                    size="small"
                    color={STATUS_COLORS[status] ?? 'default'}
                    variant={status === 'not-started' ? 'outlined' : 'filled'}
                  />
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

export default GameStatusListView;
