import React from 'react';
import {
  Button,
  Dialog,
  DialogActions,
  DialogContent,
  DialogContentText,
  DialogTitle,
  List,
  ListItem,
  ListItemText,
} from '@mui/material';

export interface ChangedGame { id: string; name: string }

interface Props {
  open: boolean;
  // "Skip": commit pending edits without recomputing the leaderboard.
  onSkip: () => void;
  // "Apply": commit pending edits AND bundle the leaderboard recompute
  // into the same save commit.
  onApply: () => void;
  changedGames: ChangedGame[];
}

export const RecomputeLeaderboardDialog: React.FC<Props> = ({
  open, onSkip, onApply, changedGames,
}) => {
  return (
    <Dialog open={open} onClose={onSkip}>
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
      </DialogContent>
      <DialogActions>
        <Button onClick={onSkip}>Salva senza aggiornare</Button>
        <Button onClick={onApply} variant="contained">Salva e aggiorna</Button>
      </DialogActions>
    </Dialog>
  );
};

export default RecomputeLeaderboardDialog;
