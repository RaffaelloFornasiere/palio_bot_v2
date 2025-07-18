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
import { useNavigate, useParams } from 'react-router-dom';
import { 
  getPalioGamesStatusForYear,
  getLeaderboardDataForYear,
  getPalioDataForYear
} from '../../../utils/yearApi';
import { 
  PalioGamesStatus, 
  PalioData, 
  Leaderboard, 
  ScoreBasedGameStatus, 
  RoundRobinGameStatus,
  ScoreBasedDivision,
  RoundRobinDivision
} from '../../../generated/types.gen';
import YearSelector from '../../../components/YearSelector';

type GameData = ScoreBasedGameStatus | RoundRobinGameStatus;
type GameDivision = ScoreBasedDivision | RoundRobinDivision;
type GameScore = { [key: string]: number | string };

const GiochiPage: React.FC = () => {
  const [gamesData, setGamesData] = useState<PalioGamesStatus | null>(null);
  const [leaderboardData, setLeaderboardData] = useState<Leaderboard | null>(null);
  const [palioData, setPalioData] = useState<PalioData | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const { year: urlYear } = useParams<{ year?: string }>();
  const navigate = useNavigate();
  
  // Initialize selectedYear from URL parameter immediately
  const [selectedYear, setSelectedYear] = useState<number | undefined>(() => {
    if (urlYear && !isNaN(Number(urlYear))) {
      return Number(urlYear);
    }
    return undefined;
  });

  useEffect(() => {
    const fetchData = async () => {
      try {
        setLoading(true);
        const [gamesResponse, leaderboardResponse, palioResponse] = await Promise.all([
          getPalioGamesStatusForYear(selectedYear),
          getLeaderboardDataForYear(selectedYear),
          getPalioDataForYear(selectedYear)
        ]);

        if (gamesResponse.error || leaderboardResponse.error || palioResponse.error) {
          throw new Error('Failed to fetch data');
        }

        setGamesData(gamesResponse.data!);
        setLeaderboardData(leaderboardResponse.data!);
        setPalioData(palioResponse.data!);
      } catch (err) {
        setError(err instanceof Error ? err.message : 'An error occurred');
      } finally {
        setLoading(false);
      }
    };

    fetchData();
  }, [selectedYear]);

  const getGameName = (gameId: string): string => {
    // First check palio data for the game name
    const palioGame = palioData?.games.find(game => game.id === gameId);
    if (palioGame) {
      return palioGame.name;
    }
    
    // Fallback: construct name from game ID
    return `Gioco ${gameId}`;
  };

  const getWinner = (gameData: GameData): string => {
    if (gameData.status !== 'completed') {
      return '-';
    }

    // Handle games with divisions
    if (gameData.divisions && gameData.divisions.length > 0) {
      const completedDivisions = (gameData.divisions as any[]).filter((div: any) => div.status === 'completed');
      if (completedDivisions.length === 0) {
        return '-';
      }
      
      const winners = completedDivisions.map((div: any) => {
        if (div.scores) {
          const numericScores = Object.entries(div.scores)
            .filter(([_, score]) => typeof score === 'number')
            .map(([village, score]) => [village, score as number]) as [string, number][];
          
          if (numericScores.length > 0) {
            const maxScore = Math.max(...numericScores.map(([_, score]) => score as number));
            const winner = numericScores.find(([_, score]) => score === maxScore);
            return winner ? `${winner[0]} (${div.name})` : `- (${div.name})`;
          }
        }
        return `- (${div.name})`;
      });
      
      return winners.join(', ');
    }

    // Handle games without divisions
    if (!('scores' in gameData) || !gameData.scores) {
      return '-';
    }

    const numericScores = Object.entries(gameData.scores)
      .filter(([_, score]) => typeof score === 'number')
      .map(([village, score]) => [village, score as number]) as [string, number][];
    
    if (numericScores.length === 0) {
      return '-';
    }
    
    const maxScore = Math.max(...numericScores.map(([_, score]) => score as number));
    const winner = numericScores.find(([_, score]) => score === maxScore);
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
    const statusOrder: { [key: string]: number } = {
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
        <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', mb: 3 }}>
          <Typography variant="h4" component="h1">
            Giochi del Palio
          </Typography>
          <YearSelector 
            selectedYear={selectedYear}
            onYearChange={(year) => {
              setSelectedYear(year);
              // Update URL to reflect year selection
              if (year) {
                navigate(`/giochi/${year}/overview`);
              } else {
                navigate('/giochi');
              }
            }}
          />
        </Box>
        
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
                {gameData.divisions && gameData.divisions.length > 0 && (
                  <Box sx={{ mb: 2 }}>
                    <Typography variant="body2" color="text.secondary" gutterBottom>
                      <strong>Divisioni:</strong>
                    </Typography>
                    {(gameData.divisions as any[]).map((division: any, index: number) => (
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