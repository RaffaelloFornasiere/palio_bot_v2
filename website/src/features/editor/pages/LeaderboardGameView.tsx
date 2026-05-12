import React from 'react';
import { useParams } from 'react-router-dom';
import { Alert, Box, Typography } from '@mui/material';
import { JsonForm } from '../components/JsonForm';
import { singleGameLeaderboardHint } from '../schema';
import { useLeaderboardContext } from './EditLeaderboardPage';

const LeaderboardGameView: React.FC = () => {
  const { gameId } = useParams<{ gameId: string }>();
  const { content, setContent, villages } = useLeaderboardContext();

  if (!gameId) return null;

  const game = content.game_leaderboards?.[gameId];
  if (game == null) {
    return (
      <Alert severity="warning">
        Classifica non trovata per questo gioco.
      </Alert>
    );
  }

  return (
    <Box>
      <Typography variant="h6" sx={{ mb: 2 }}>
        {game.game_name || '(senza nome)'}
      </Typography>
      <Alert severity="info" sx={{ mb: 2 }}>
        Bonus e penalità si gestiscono in Stato giochi: la classifica viene
        ricalcolata da quei valori. Modifiche manuali qui verranno sovrascritte
        al prossimo ricalcolo.
      </Alert>
      <JsonForm
        value={game}
        onChange={(nv) =>
          setContent((prev) => ({
            ...prev,
            game_leaderboards: { ...(prev.game_leaderboards ?? {}), [gameId]: nv },
          }))
        }
        hint={singleGameLeaderboardHint}
        villages={villages}
      />
    </Box>
  );
};

export default LeaderboardGameView;
