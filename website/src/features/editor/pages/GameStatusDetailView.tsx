import React from 'react';
import { useParams } from 'react-router-dom';
import { Alert, Box, Typography } from '@mui/material';
import { JsonForm } from '../components/JsonForm';
import { singleGameStatusHint } from '../schema';
import { useGameStatusContext } from './EditGameStatusPage';

const GameStatusDetailView: React.FC = () => {
  const { gameId } = useParams<{ gameId: string }>();
  const { content, setContent, villages, games } = useGameStatusContext();

  if (!gameId) return null;

  const gameData = content.game_scores?.[gameId];
  const gameMeta = games.find((g) => g.id === gameId);

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
        hint={singleGameStatusHint}
        villages={villages}
      />
    </Box>
  );
};

export default GameStatusDetailView;
