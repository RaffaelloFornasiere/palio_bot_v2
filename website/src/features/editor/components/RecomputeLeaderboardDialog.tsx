import React, { useState } from 'react';
import {
  Alert,
  Box,
  Button,
  CircularProgress,
  Dialog,
  DialogActions,
  DialogContent,
  DialogContentText,
  DialogTitle,
  List,
  ListItem,
  ListItemText,
  Typography,
} from '@mui/material';
import { editorApi } from '../api/client';

export interface ChangedGame { id: string; name: string }

interface Props {
  open: boolean;
  onClose: () => void;
  proposed: any;
  changedGames: ChangedGame[];
}

export const RecomputeLeaderboardDialog: React.FC<Props> = ({
  open, onClose, proposed, changedGames,
}) => {
  const [applying, setApplying] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const handleApply = async () => {
    setApplying(true);
    setError(null);
    try {
      await editorApi.applyLeaderboard(proposed);
      onClose();
    } catch (e: any) {
      setError(e?.message ?? 'errore applicazione');
    } finally {
      setApplying(false);
    }
  };

  if (applying) {
    return (
      <Dialog open={open}>
        <DialogContent>
          <Box sx={{ display: 'flex', alignItems: 'center', gap: 2, py: 2 }}>
            <CircularProgress size={20} />
            <Typography>Aggiornamento in corso…</Typography>
          </Box>
        </DialogContent>
      </Dialog>
    );
  }

  return (
    <Dialog open={open} onClose={onClose}>
      <DialogTitle>Aggiornare la classifica?</DialogTitle>
      <DialogContent>
        <DialogContentText sx={{ mb: 1 }}>
          Verranno aggiornati i seguenti giochi:
        </DialogContentText>
        <List dense>
          {changedGames.map((g) => (
            <ListItem key={g.id} disableGutters>
              <ListItemText primary={g.name} />
            </ListItem>
          ))}
        </List>
        {error && <Alert severity="error" sx={{ mt: 2 }}>{error}</Alert>}
      </DialogContent>
      <DialogActions>
        <Button onClick={onClose}>Annulla</Button>
        <Button onClick={handleApply} variant="contained">Applica</Button>
      </DialogActions>
    </Dialog>
  );
};

export default RecomputeLeaderboardDialog;
