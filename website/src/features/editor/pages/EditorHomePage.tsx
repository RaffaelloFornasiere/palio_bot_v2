import React from 'react';
import { useNavigate } from 'react-router-dom';
import {
  Box, Container, Typography, Card, CardActionArea, CardContent, Stack, Button, AppBar, Toolbar,
} from '@mui/material';
import LeaderboardIcon from '@mui/icons-material/Leaderboard';
import SportsEsportsIcon from '@mui/icons-material/SportsEsports';
import LogoutIcon from '@mui/icons-material/Logout';
import { useAuthStore } from '../store/authStore';

const EditorHomePage: React.FC = () => {
  const navigate = useNavigate();
  const { signOut, user } = useAuthStore();

  return (
    <Box sx={{ minHeight: '100vh', bgcolor: 'background.default' }}>
      <AppBar position="sticky" color="default" elevation={1}>
        <Toolbar>
          <Typography variant="h6" sx={{ flexGrow: 1 }}>Editor manuale</Typography>
          {user && (
            <Typography variant="body2" color="text.secondary" sx={{ mr: 2, display: { xs: 'none', sm: 'block' } }}>
              {user.email}
            </Typography>
          )}
          <Button
            startIcon={<LogoutIcon />}
            onClick={async () => { await signOut(); navigate('/edit/login', { replace: true }); }}
            size="small"
          >
            Esci
          </Button>
        </Toolbar>
      </AppBar>
      <Container maxWidth="sm" sx={{ py: 3 }}>
        <Typography variant="body2" color="text.secondary" sx={{ mb: 2 }}>
          Usa questa sezione solo per correggere manualmente i dati quando
          l'agente AI li ha modificati in modo errato. Le modifiche vengono
          validate dai modelli del backend.
        </Typography>
        <Stack spacing={2}>
          <Card>
            <CardActionArea onClick={() => navigate('/edit/leaderboard')}>
              <CardContent sx={{ display: 'flex', alignItems: 'center', gap: 2 }}>
                <LeaderboardIcon color="primary" fontSize="large" />
                <Box>
                  <Typography variant="h6">Classifica</Typography>
                  <Typography variant="body2" color="text.secondary">
                    Modifica leaderboard.json
                  </Typography>
                </Box>
              </CardContent>
            </CardActionArea>
          </Card>
          <Card>
            <CardActionArea onClick={() => navigate('/edit/games')}>
              <CardContent sx={{ display: 'flex', alignItems: 'center', gap: 2 }}>
                <SportsEsportsIcon color="primary" fontSize="large" />
                <Box>
                  <Typography variant="h6">Stato giochi</Typography>
                  <Typography variant="body2" color="text.secondary">
                    Modifica palio_games_status.json
                  </Typography>
                </Box>
              </CardContent>
            </CardActionArea>
          </Card>
        </Stack>
      </Container>
    </Box>
  );
};

export default EditorHomePage;
