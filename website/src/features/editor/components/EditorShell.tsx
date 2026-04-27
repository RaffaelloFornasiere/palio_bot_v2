import React from 'react';
import { useNavigate } from 'react-router-dom';
import {
  AppBar, Toolbar, IconButton, Typography, Box, Container, Alert, CircularProgress, Button, Stack,
} from '@mui/material';
import ArrowBackIcon from '@mui/icons-material/ArrowBack';
import RefreshIcon from '@mui/icons-material/Refresh';
import SaveBar from './SaveBar';
import { UseEditorSession } from '../hooks/useEditorSession';

interface Props<T> {
  title: string;
  session: UseEditorSession<T>;
  children: (content: T) => React.ReactNode;
}

export function EditorShell<T>({ title, session, children }: Props<T>) {
  const navigate = useNavigate();
  const {
    loading, content, error, externallyChanged, dirty, saving, committing,
    saveAndCommit, discard,
  } = session;

  const handleBack = async () => {
    if (dirty && !window.confirm('Modifiche non salvate. Uscire comunque?')) return;
    await discard();
    navigate('/edit', { replace: true });
  };

  const handleCommit = async () => {
    try {
      await saveAndCommit();
      navigate('/edit', { replace: true });
    } catch {
      // error / externallyChanged already in session state
    }
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
    </Box>
  );
}
