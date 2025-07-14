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

interface GameDivision {
  name: string;
  status: 'completed' | 'in-progress' | 'not-started';
  scores?: GameScore;
  rounds?: GameRound[];
}

interface GameData {
  status: 'completed' | 'in-progress' | 'not-started';
  scores?: GameScore;
  rounds?: GameRound[];
  divisions?: GameDivision[];
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

interface PalioGame {
  id: string;
  name: string;
  type: string;
  description: string;
  measure_unit: string;
  lower_is_better: boolean;
  dates: Array<{
    start_datetime: string;
    end_datetime: string;
    subtitle?: string;
  }>;
}

interface PalioData {
  competition_name: string;
  villages: string[];
  games: PalioGame[];
  non_game_events: any[];
}

const GiochiPage: React.FC = () => {
  const [gamesData, setGamesData] = useState<GamesStatusData | null>(null);
  const [leaderboardData, setLeaderboardData] = useState<LeaderboardData | null>(null);
  const [palioData, setPalioData] = useState<PalioData | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const navigate = useNavigate();

  useEffect(() => {
    const fetchData = async () => {
      try {
        setLoading(true);
        const [gamesResponse, leaderboardResponse, palioResponse] = await Promise.all([
          apiCall('/palio_games_status'),
          apiCall('/leaderboard'),
          apiCall('/palio')
        ]);

        if (!gamesResponse.ok || !leaderboardResponse.ok || !palioResponse.ok) {
          throw new Error('Failed to fetch data');
        }

        const gamesData = await gamesResponse.json();
        const leaderboardData = await leaderboardResponse.json();
        const palioData = await palioResponse.json();

        setGamesData(gamesData);
        setLeaderboardData(leaderboardData);
        setPalioData(palioData);
      } catch (err) {
        setError(err instanceof Error ? err.message : 'An error occurred');
      } finally {
        setLoading(false);
      }
    };

    fetchData();
  }, []);

  const getGameName = (gameId: string): string => {
    // First check palio data for the game name
    const palioGame = palioData?.games.find(game => game.id === gameId);
    if (palioGame) {
      return palioGame.name;
    }
    
    // Fallback to leaderboard data
    return leaderboardData?.game_leaderboards[gameId]?.name || `Gioco ${gameId}`;
  };

  const getWinner = (gameData: GameData): string => {
    if (gameData.status !== 'completed') {
      return '-';
    }

    // Handle games with divisions
    if (gameData.divisions) {
      const completedDivisions = gameData.divisions.filter(div => div.status === 'completed');
      if (completedDivisions.length === 0) {
        return '-';
      }
      
      const winners = completedDivisions.map(div => {
        if (div.scores) {
          const maxScore = Math.max(...Object.values(div.scores));
          const winner = Object.entries(div.scores).find(([_, score]) => score === maxScore);
          return winner ? `${winner[0]} (${div.name})` : `- (${div.name})`;
        }
        return `- (${div.name})`;
      });
      
      return winners.join(', ');
    }

    // Handle games without divisions
    if (!gameData.scores) {
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

  const sortGamesByStatus = (games: [string, GameData][]): [string, GameData][] => {
    const statusOrder = {
      'in-progress': 1,
      'completed': 2,
      'not-started': 3
    };

    return games.sort(([, gameA], [, gameB]) => {
      const orderA = statusOrder[gameA.status] || 4;
      const orderB = statusOrder[gameB.status] || 4;
      return orderA - orderB;
    });
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
          {gamesData && sortGamesByStatus(Object.entries(gamesData.game_scores)).map(([gameId, gameData]) => (

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

                {/* Show divisions if they exist */}
                {gameData.divisions && (
                  <Box sx={{ mb: 2 }}>
                    <Typography variant="body2" color="text.secondary" gutterBottom>
                      <strong>Divisioni:</strong>
                    </Typography>
                    {gameData.divisions.map((division, index) => (
                      <Box key={index} sx={{ ml: 1, mb: 1 }}>
                        <Chip 
                          label={`${division.name}: ${getStatusText(division.status)}`}
                          color={getStatusColor(division.status) as any}
                          size="small"
                          variant="outlined"
                        />
                      </Box>
                    ))}
                  </Box>
                )}

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