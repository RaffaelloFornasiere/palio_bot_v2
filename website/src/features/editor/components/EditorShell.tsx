import React, { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import {
  AppBar, Toolbar, IconButton, Typography, Box, Container, Alert, CircularProgress, Button, Stack,
} from '@mui/material';
import ArrowBackIcon from '@mui/icons-material/ArrowBack';
import RefreshIcon from '@mui/icons-material/Refresh';
import SaveBar from './SaveBar';
import RecomputeLeaderboardDialog, { ChangedGame } from './RecomputeLeaderboardDialog';
import { editorApi } from '../api/client';
import { UseEditorSession } from '../hooks/useEditorSession';

interface Props<T> {
  title: string;
  session: UseEditorSession<T>;
  children: (content: T) => React.ReactNode;
  // Override the top-bar back button. When provided, the default
  // (confirm + discard + navigate to /edit) is bypassed entirely —
  // useful for in-editor navigation (e.g. detail → list) that should
  // preserve the open session.
  onBack?: () => void | Promise<void>;
  // When set, after a successful commit the user is prompted to also
  // recompute the leaderboard. Use for files whose changes affect the
  // leaderboard (palio_games_status, palio).
  promptRecomputeLeaderboard?: boolean;
}

export function EditorShell<T>({
  title, session, children, onBack, promptRecomputeLeaderboard,
}: Props<T>) {
  const navigate = useNavigate();
  const {
    loading, content, error, externallyChanged, dirty, saving, committing,
    saveAndCommit, discard,
  } = session;

  const handleBack = async () => {
    if (onBack) {
      await onBack();
      return;
    }
    if (dirty && !window.confirm('Modifiche non salvate. Uscire comunque?')) return;
    await discard();
    navigate('/edit', { replace: true });
  };

  const [recompute, setRecompute] = useState<{
    proposed: any;
    changedGames: ChangedGame[];
  } | null>(null);

  const handleCommit = async () => {
    try {
      await saveAndCommit();
      if (!promptRecomputeLeaderboard) {
        navigate('/edit', { replace: true });
        return;
      }
      // Auto-preview: only bother the user if something actually changed.
      let preview;
      try {
        preview = await editorApi.previewLeaderboard();
      } catch {
        navigate('/edit', { replace: true });
        return;
      }
      if (!preview.changed_games?.length) {
        navigate('/edit', { replace: true });
        return;
      }
      setRecompute({
        proposed: preview.proposed,
        changedGames: preview.changed_games,
      });
    } catch {
      // error / externallyChanged already in session state
    }
  };

  const handleRecomputeClose = () => {
    setRecompute(null);
    navigate('/edit', { replace: true });
  };

  const handleDiscard = async () => {
    if (dirty && !window.confirm('Annullare tutte le modifiche?')) return;
    await discard();
    navigate('/edit', { replace: true });
  };

  const reopen = () => {
    navigate(0); // full reload to re-run openSession
  };

  return (
    <Box sx={{ minHeight: '100vh', display: 'flex', flexDirection: 'column', bgcolor: 'background.default' }}>
      <AppBar position="sticky" color="default" elevation={1}>
        <Toolbar>
          <IconButton edge="start" onClick={handleBack} aria-label="indietro">
            <ArrowBackIcon />
          </IconButton>
          <Typography variant="h6" sx={{ flexGrow: 1 }} noWrap>{title}</Typography>
        </Toolbar>
      </AppBar>

      <Container maxWidth="md" sx={{ flex: 1, py: 2, pb: 10 }}>
        {loading && (
          <Box sx={{ display: 'flex', justifyContent: 'center', py: 4 }}>
            <CircularProgress />
          </Box>
        )}

        {externallyChanged && (
          <Stack spacing={2} alignItems="center" sx={{ py: 4 }}>
            <Alert severity="warning" sx={{ width: '100%' }}>
              {externallyChanged}
            </Alert>
            <Stack direction="row" spacing={1}>
              <Button onClick={() => navigate('/edit', { replace: true })} variant="outlined">
                Torna indietro
              </Button>
              <Button startIcon={<RefreshIcon />} onClick={reopen} variant="contained">
                Ricarica ultimo stato
              </Button>
            </Stack>
          </Stack>
        )}

        {error && !externallyChanged && (
          <Alert severity="error" sx={{ mb: 2 }}>{error}</Alert>
        )}

        {!loading && !externallyChanged && content != null && children(content)}
      </Container>

      {!loading && !externallyChanged && content != null && (
        <SaveBar
          dirty={dirty}
          saving={saving}
          committing={committing}
          onCommit={handleCommit}
          onDiscard={handleDiscard}
        />
      )}

      <RecomputeLeaderboardDialog
        open={recompute != null}
        onClose={handleRecomputeClose}
        proposed={recompute?.proposed}
        changedGames={recompute?.changedGames ?? []}
      />
    </Box>
  );
}
