import React from 'react';
import { Link as RouterLink } from 'react-router-dom';
import { Alert, Button, Box } from '@mui/material';
import { useEditorSession } from '../hooks/useEditorSession';
import { EditorShell } from '../components/EditorShell';
import { JsonForm } from '../components/JsonForm';
import { leaderboardSchema } from '../schema';

interface Leaderboard {
  villages: string[];
  palio_leaderboard: Record<string, { points: number; position: number }>;
  game_leaderboards: Record<string, any>;
}

const EditLeaderboardPage: React.FC = () => {
  const session = useEditorSession<Leaderboard>('leaderboard', 'manual_edit_leaderboard');

  return (
    <EditorShell title="Classifica" session={session}>
      {(content) => (
        <Box>
          <Alert
            severity="info"
            sx={{ mb: 2 }}
            action={
              <Button component={RouterLink} to="/edit/games" size="small" color="inherit">
                Apri Stato giochi
              </Button>
            }
          >
            Bonus e penalità si gestiscono in Stato giochi: la classifica viene
            ricalcolata da quei valori.
          </Alert>
          <JsonForm
            value={content}
            onChange={(nv) => session.setContent(() => nv)}
            hint={leaderboardSchema}
            villages={content.villages ?? []}
          />
        </Box>
      )}
    </EditorShell>
  );
};

export default EditLeaderboardPage;
