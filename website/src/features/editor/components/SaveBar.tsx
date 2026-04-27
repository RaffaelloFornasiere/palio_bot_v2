import React from 'react';
import { Paper, Button, Stack, Typography, CircularProgress } from '@mui/material';
import SaveIcon from '@mui/icons-material/Save';
import CancelIcon from '@mui/icons-material/Cancel';

interface Props {
  dirty: boolean;
  saving: boolean;
  committing: boolean;
  onCommit: () => void;
  onDiscard: () => void;
}

const SaveBar: React.FC<Props> = ({ dirty, saving, committing, onCommit, onDiscard }) => {
  const busy = saving || committing;
  return (
    <Paper
      elevation={8}
      sx={{
        position: 'sticky',
        bottom: 0,
        left: 0,
        right: 0,
        p: 1.5,
        display: 'flex',
        alignItems: 'center',
        gap: 1,
        borderRadius: 0,
        zIndex: 10,
      }}
    >
      <Typography variant="body2" color={dirty ? 'warning.main' : 'text.secondary'} sx={{ flex: 1 }}>
        {dirty ? 'Modifiche non salvate' : 'Nessuna modifica'}
      </Typography>
      <Stack direction="row" spacing={1}>
        <Button
          startIcon={<CancelIcon />}
          onClick={onDiscard}
          disabled={busy}
          color="inherit"
        >
          Annulla
        </Button>
        <Button
          variant="contained"
          startIcon={busy ? <CircularProgress size={18} color="inherit" /> : <SaveIcon />}
          onClick={onCommit}
          disabled={busy || !dirty}
        >
          Salva
        </Button>
      </Stack>
    </Paper>
  );
};

export default SaveBar;
