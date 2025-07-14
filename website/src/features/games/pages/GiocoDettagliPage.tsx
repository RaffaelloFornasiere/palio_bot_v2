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
  Alert,
  Table,
  TableBody,
  TableCell,
  TableContainer,
  TableHead,
  TableRow,
  Paper,
  Divider
} from '@mui/material';
import { useParams, useNavigate } from 'react-router-dom';
import { apiCall } from '../../../utils/api';
import { ArrowBack } from '@mui/icons-material';

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

const GiocoDettagliPage: React.FC = () => {
  const { gameId } = useParams<{ gameId: string }>();
  const navigate = useNavigate();
  const [gamesData, setGamesData] = useState<GamesStatusData | null>(null);
  const [leaderboardData, setLeaderboardData] = useState<LeaderboardData | null>(null);
  const [palioData, setPalioData] = useState<PalioData | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

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

  const getWinner = (gameData: GameData): string => {
    if (gameData.status !== 'completed' || !gameData.scores) {
      return '-';
    }

    const maxScore = Math.max(...Object.values(gameData.scores));
    const winner = Object.entries(gameData.scores).find(([_, score]) => score === maxScore);
    return winner ? winner[0] : '-';
  };

  const getSortedScores = (scores: GameScore): [string, number][] => {
    return Object.entries(scores).sort(([, a], [, b]) => b - a);
  };

  const getSortedLeaderboard = (leaderboard: GameScore): [string, number][] => {
    return Object.entries(leaderboard).sort(([, a], [, b]) => b - a);
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

  if (!gameId || !gamesData?.game_scores[gameId]) {
    return (
      <Container maxWidth="lg">
        <Box sx={{ mt: 4, mb: 4 }}>
          <Alert severity="warning">
            Gioco non trovato
          </Alert>
        </Box>
      </Container>
    );
  }

  const gameData = gamesData.game_scores[gameId];
  const gameLeaderboard = leaderboardData?.game_leaderboards[gameId];

  return (
    <Container maxWidth="lg">
      <Box sx={{ mt: 4, mb: 4 }}>
        <Box sx={{ mb: 3 }}>
          <Button
            startIcon={<ArrowBack />}
            onClick={() => navigate('/giochi')}
            sx={{ mb: 2 }}
          >
            Torna ai Giochi
          </Button>
          
          <Typography variant="h4" component="h1" gutterBottom>
            {getGameName(gameId)}
          </Typography>
          
          <Box sx={{ display: 'flex', alignItems: 'center', gap: 2, mb: 2 }}>
            <Chip 
              label={getStatusText(gameData.status)} 
              color={getStatusColor(gameData.status) as any}
            />
            <Typography variant="body2" color="text.secondary">
              ID: {gameId}
            </Typography>
          </Box>

          {gamesData && (
            <Typography variant="body2" color="text.secondary">
              Ultimo aggiornamento: {formatDate(gamesData.last_updated)}
            </Typography>
          )}
        </Box>

        <Box sx={{ display: 'flex', flexDirection: 'column', gap: 3 }}>
          {/* Game Status and Winner */}
          <Box sx={{ display: 'grid', gridTemplateColumns: { xs: '1fr', md: '1fr 1fr' }, gap: 3 }}>
            <Card>
              <CardContent>
                <Typography variant="h6" gutterBottom>
                  Informazioni Gioco
                </Typography>
                
                <Box sx={{ mb: 2 }}>
                  <Typography variant="body2" color="text.secondary">
                    <strong>Stato:</strong> {getStatusText(gameData.status)}
                  </Typography>
                </Box>

                <Box sx={{ mb: 2 }}>
                  <Typography variant="body2" color="text.secondary">
                    <strong>Vincitore:</strong> {getWinner(gameData)}
                  </Typography>
                </Box>
              </CardContent>
            </Card>

            {/* Game Leaderboard Points */}
            {gameLeaderboard && (
              <Card>
                <CardContent>
                  <Typography variant="h6" gutterBottom>
                    Punti Classifica
                  </Typography>
                  
                  <TableContainer>
                    <Table size="small">
                      <TableHead>
                        <TableRow>
                          <TableCell>Posizione</TableCell>
                          <TableCell>Borgo</TableCell>
                          <TableCell align="right">Punti</TableCell>
                        </TableRow>
                      </TableHead>
                      <TableBody>
                        {getSortedLeaderboard(gameLeaderboard.leaderboard).map(([village, points], index) => (
                          <TableRow key={village}>
                            <TableCell>{index + 1}</TableCell>
                            <TableCell>{village}</TableCell>
                            <TableCell align="right">{points}</TableCell>
                          </TableRow>
                        ))}
                      </TableBody>
                    </Table>
                  </TableContainer>
                </CardContent>
              </Card>
            )}
          </Box>

          {/* Game Scores */}
          {gameData.scores && (
            <Card>
              <CardContent>
                <Typography variant="h6" gutterBottom>
                  Punteggi Finali
                </Typography>
                
                <TableContainer component={Paper} variant="outlined">
                  <Table>
                    <TableHead>
                      <TableRow>
                        <TableCell>Posizione</TableCell>
                        <TableCell>Borgo</TableCell>
                        <TableCell align="right">Punteggio</TableCell>
                      </TableRow>
                    </TableHead>
                    <TableBody>
                      {getSortedScores(gameData.scores).map(([village, score], index) => (
                        <TableRow key={village}>
                          <TableCell>
                            <Typography variant="body1" fontWeight={index === 0 ? 'bold' : 'normal'}>
                              {index + 1}
                            </Typography>
                          </TableCell>
                          <TableCell>
                            <Typography variant="body1" fontWeight={index === 0 ? 'bold' : 'normal'}>
                              {village}
                            </Typography>
                          </TableCell>
                          <TableCell align="right">
                            <Typography variant="body1" fontWeight={index === 0 ? 'bold' : 'normal'}>
                              {score}
                            </Typography>
                          </TableCell>
                        </TableRow>
                      ))}
                    </TableBody>
                  </Table>
                </TableContainer>
              </CardContent>
            </Card>
          )}

          {/* Rounds (for in-progress games) */}
          {gameData.rounds && gameData.rounds.length > 0 && (
            <Card>
              <CardContent>
                <Typography variant="h6" gutterBottom>
                  Punteggi per Round
                </Typography>
                
                {gameData.rounds.map((round, index) => (
                  <Box key={index} sx={{ mb: 2 }}>
                    <Typography variant="subtitle1" gutterBottom>
                      Round {index + 1}
                    </Typography>
                    
                    <TableContainer component={Paper} variant="outlined" sx={{ mb: 2 }}>
                      <Table size="small">
                        <TableHead>
                          <TableRow>
                            <TableCell>Borgo</TableCell>
                            <TableCell align="right">Punteggio</TableCell>
                          </TableRow>
                        </TableHead>
                        <TableBody>
                          {getSortedScores(round).map(([village, score]) => (
                            <TableRow key={village}>
                              <TableCell>{village}</TableCell>
                              <TableCell align="right">{score}</TableCell>
                            </TableRow>
                          ))}
                        </TableBody>
                      </Table>
                    </TableContainer>
                    
                    {index < gameData.rounds!.length - 1 && <Divider />}
                  </Box>
                ))}
              </CardContent>
            </Card>
          )}

        </Box>
      </Box>
    </Container>
  );
};

export default GiocoDettagliPage;