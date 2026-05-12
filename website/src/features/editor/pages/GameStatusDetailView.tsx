import React, { useMemo } from 'react';
import { useParams } from 'react-router-dom';
import { Alert, Box, Typography } from '@mui/material';
import { JsonForm } from '../components/JsonForm';
import { GameVariant, singleGameStatusHintFor } from '../schema';
import { useGameStatusContext } from './EditGameStatusPage';

const GameStatusDetailView: React.FC = () => {
  const { gameId } = useParams<{ gameId: string }>();
  const { content, setContent, villages, games } = useGameStatusContext();

  const gameData = gameId ? content.game_scores?.[gameId] : undefined;
  const gameMeta = gameId ? games.find((g) => g.id === gameId) : undefined;
  const variant = gameMeta?.type as GameVariant | undefined;
  const hint = useMemo(() => singleGameStatusHintFor(variant), [variant]);

  if (!gameId) return null;

  if (gameData == null) {
    return (
      <Alert severity="warning">
        Gioco non trovato in stato giochi.
      </Alert>
    );
  }

  return (
    <Box>
      <Typography variant="h6" sx={{ mb: 2 }}>
        {gameMeta?.name || '(senza nome)'}
      </Typography>
      <JsonForm
        value={gameData}
        onChange={(nv) =>
          setContent((prev) => ({
            ...prev,
            game_scores: { ...(prev.game_scores ?? {}), [gameId]: nv },
          }))
        }
        hint={hint}
        villages={villages}
      />
    </Box>
  );
};

export default GameStatusDetailView;
