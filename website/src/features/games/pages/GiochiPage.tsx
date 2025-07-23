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
  useTheme
} from '@mui/material';
import { useNavigate } from 'react-router-dom';
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
} from '../../../generated';
import { useYear } from '../../../contexts/YearContext';
import YearSelector from '../../../components/YearSelector';
import { getStatusText, formatDate, getStatusColor } from '../utils';
import { getVillageBackgroundColor } from '../../../utils/colorUtils';

type GameData = ScoreBasedGameStatus | RoundRobinGameStatus;
type GameDivision = ScoreBasedDivision | RoundRobinDivision;
type GameScore = { [key: string]: number | string };

const GiochiPage: React.FC = () => {
  const [gamesData, setGamesData] = useState<PalioGamesStatus | null>(null);
  const [leaderboardData, setLeaderboardData] = useState<Leaderboard | null>(null);
  const [palioData, setPalioData] = useState<PalioData | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const { selectedYear } = useYear();
  const navigate = useNavigate();
  const theme = useTheme();

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

  const getWinner = (gameId: string): string => {
    const overallLeaderboard = leaderboardData?.game_leaderboards[gameId]?.overall_leaderboard ?? {};
    return Object.entries(overallLeaderboard).find(i => i[1].position === 1)?.[0] ?? ''
  };

  const getVillageColor = (village: string): string | undefined => {
    return palioData?.villages_colors?.[village];
  };

  const getWinnerBackgroundColor = (village: string): string | undefined => {
    if (!village) return undefined;
    const villageColor = getVillageColor(village);
    if (!villageColor) return undefined;
    
    // Get the current theme background color
    const backgroundColor = theme.palette.mode === 'dark' ? '#121212' : '#ffffff';
    return getVillageBackgroundColor(villageColor, backgroundColor, 0.4);
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
          <YearSelector />
        </Box>
        
        {gamesData && (
          <Typography variant="body2" color="text.secondary" sx={{ mb: 3 }}>
            Ultimo aggiornamento: {formatDate(gamesData.last_updated)}
          </Typography>
        )}

        <Box sx={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(300px, 1fr))', gap: 3 }}>
          {gamesData && sortGamesByStatus(Object.entries(gamesData.game_scores)).map(([gameId, gameData]) => {
            const winner = getWinner(gameId);
            const winnerBgColor = getWinnerBackgroundColor(winner);
            
            return (
              <Card 
                key={gameId} 
                sx={{ 
                  height: '100%',
                  backgroundColor: winnerBgColor || 'inherit',
                  transition: 'background-color 0.3s ease'
                }}
              >
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

                  <Box sx={{ mb: 1, display: 'flex', alignItems: 'center', gap: 1 }}>
                    <Typography variant="body2" color="text.secondary">
                      <strong>Vincitore:</strong>
                    </Typography>
                    {winner && (
                      <Chip 
                        label={winner}
                        size="small"
                        sx={{ 
                          backgroundColor: getVillageColor(winner) || 'default',
                          color: '#fff',
                          fontWeight: 'bold'
                        }}
                      />
                    )}
                    {!winner && (
                      <Typography variant="body2" color="text.secondary">
                        -
                      </Typography>
                    )}
                  </Box>

                  <Typography variant="body2" color="text.secondary" gutterBottom>
                    <strong>ID Gioco:</strong> {gameId}
                  </Typography>

                  <Box sx={{ mt: 2 }}>
                    <Button 
                      variant="outlined" 
                      size="small"
                      onClick={() => navigate(selectedYear ? `/${selectedYear}/giochi/${gameId}` : `/giochi/${gameId}`)}
                    >
                      Vedi Dettagli
                    </Button>
                  </Box>
                </CardContent>
              </Card>
            );
          })}
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