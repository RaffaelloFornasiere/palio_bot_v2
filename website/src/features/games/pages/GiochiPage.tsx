import React, { useState, useEffect } from 'react';
import { 
  Container, 
  Typography, 
  Box, 
  Card, 
  CardContent, 
  Chip, 
  Button,
  CircularProgress,
  Alert
} from '@mui/material';
import { useNavigate } from 'react-router-dom';
import { apiCall } from '../../../utils/api';

interface GameScore {
  [village: string]: number;
}

interface GameRound {
  [village: string]: number;
}

interface GameData {
  status: 'completed' | 'in-progress' | 'not-started';
  scores?: GameScore;
  rounds?: GameRound[];
}

interface GameLeaderboard {
  name: string;
  leaderboard: GameScore;
}

interface GamesStatusData {
  game_scores: {
    [gameId: string]: GameData;
  };
  last_updated: string;
}

interface LeaderboardData {
  villages: string[];
  points: GameScore;
  game_leaderboards: {
    [gameId: string]: GameLeaderboard;
  };
}

const GiochiPage: React.FC = () => {
  const [gamesData, setGamesData] = useState<GamesStatusData | null>(null);
  const [leaderboardData, setLeaderboardData] = useState<LeaderboardData | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const navigate = useNavigate();

  useEffect(() => {
    const fetchData = async () => {
      try {
        setLoading(true);
        const [gamesResponse, leaderboardResponse] = await Promise.all([
          apiCall('/palio_games_status'),
          apiCall('/leaderboard')
        ]);

        if (!gamesResponse.ok || !leaderboardResponse.ok) {
          throw new Error('Failed to fetch data');
        }

        const gamesData = await gamesResponse.json();
        const leaderboardData = await leaderboardResponse.json();

        setGamesData(gamesData);
        setLeaderboardData(leaderboardData);
      } catch (err) {
        setError(err instanceof Error ? err.message : 'An error occurred');
      } finally {
        setLoading(false);
      }
    };

    fetchData();
  }, []);

  const getGameName = (gameId: string): string => {
    return leaderboardData?.game_leaderboards[gameId]?.name || `Gioco ${gameId}`;
  };

  const getWinner = (gameData: GameData): string => {
    if (gameData.status !== 'completed' || !gameData.scores) {
      return '-';
    }

    const maxScore = Math.max(...Object.values(gameData.scores));
    const winner = Object.entries(gameData.scores).find(([_, score]) => score === maxScore);
    return winner ? winner[0] : '-';
  };

  const getStatusColor = (status: string) => {
    switch (status) {
      case 'completed':
        return 'success';
      case 'in-progress':
        return 'warning';
      case 'not-started':
        return 'default';
      default:
        return 'default';
    }
  };

  const getStatusText = (status: string) => {
    switch (status) {
      case 'completed':
        return 'Completato';
      case 'in-progress':
        return 'In corso';
      case 'not-started':
        return 'Non iniziato';
      default:
        return 'Sconosciuto';
    }
  };

  const formatDate = (dateString: string): string => {
    try {
      const date = new Date(dateString);
      return date.toLocaleDateString('it-IT', {
        year: 'numeric',
        month: 'short',
        day: 'numeric',
        hour: '2-digit',
        minute: '2-digit'
      });
    } catch {
      return 'Data non disponibile';
    }
  };

  if (loading) {
    return (
      <Container maxWidth="lg">
        <Box sx={{ mt: 4, mb: 4, display: 'flex', justifyContent: 'center' }}>
          <CircularProgress />
        </Box>
      </Container>
    );
  }

  if (error) {
    return (
      <Container maxWidth="lg">
        <Box sx={{ mt: 4, mb: 4 }}>
          <Alert severity="error">
            Errore nel caricamento dei dati: {error}
          </Alert>
        </Box>
      </Container>
    );
  }

  return (
    <Container maxWidth="lg">
      <Box sx={{ mt: 4, mb: 4 }}>
        <Typography variant="h4" component="h1" gutterBottom>
          Giochi del Palio
        </Typography>
        
        {gamesData && (
          <Typography variant="body2" color="text.secondary" sx={{ mb: 3 }}>
            Ultimo aggiornamento: {formatDate(gamesData.last_updated)}
          </Typography>
        )}

        <Box sx={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(300px, 1fr))', gap: 3 }}>
          {gamesData && Object.entries(gamesData.game_scores).map(([gameId, gameData]) => (
            <Card key={gameId} sx={{ height: '100%' }}>
              <CardContent>
                <Typography variant="h6" component="h2" gutterBottom>
                  {getGameName(gameId)}
                </Typography>
                
                <Box sx={{ mb: 2 }}>
                  <Chip 
                    label={getStatusText(gameData.status)} 
                    color={getStatusColor(gameData.status) as any}
                    size="small"
                  />
                </Box>

                <Typography variant="body2" color="text.secondary" gutterBottom>
                  <strong>Vincitore:</strong> {getWinner(gameData)}
                </Typography>

                <Typography variant="body2" color="text.secondary" gutterBottom>
                  <strong>ID Gioco:</strong> {gameId}
                </Typography>

                <Box sx={{ mt: 2 }}>
                  <Button 
                    variant="outlined" 
                    size="small"
                    onClick={() => navigate(`/giochi/${gameId}`)}
                  >
                    Vedi Dettagli
                  </Button>
                </Box>
              </CardContent>
            </Card>
          ))}
        </Box>

        {(!gamesData || Object.keys(gamesData.game_scores).length === 0) && (
          <Box sx={{ mt: 4, textAlign: 'center' }}>
            <Typography variant="body1" color="text.secondary">
              Nessun gioco disponibile al momento.
            </Typography>
          </Box>
        )}
      </Box>
    </Container>
  );
};

export default GiochiPage;