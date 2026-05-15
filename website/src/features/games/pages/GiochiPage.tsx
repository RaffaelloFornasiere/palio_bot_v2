import React, { useState, useEffect } from 'react';
import { 
  Container, 
  Typography, 
  Box, 
  Card, 
  CardContent, 
  Chip,
  CircularProgress,
  Alert,
  useTheme
} from '@mui/material';
import { alpha } from '@mui/material/styles';
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
} from '../../../generated';
import { useYear } from '../../../contexts/YearContext';
import YearSelector from '../../../components/YearSelector';
import { getStatusText, formatDate, getStatusColor } from '../utils';
import { curatedVillageColor } from '../../../utils/colorUtils';
import VillageToken from '../../../components/VillageToken';

type GameData = ScoreBasedGameStatus | RoundRobinGameStatus;

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

        <Box
          sx={{
            display: 'grid',
            gridTemplateColumns: { xs: '1fr', sm: 'repeat(auto-fill, minmax(290px, 1fr))' },
            gap: 2.5,
          }}
        >
          {gamesData && sortGamesByStatus(Object.entries(gamesData.game_scores)).map(([gameId, gameData]) => {
            const winner = getWinner(gameId);
            const winnerColor = getVillageColor(winner);
            const statusAccent =
              gameData.status === 'completed' ? theme.palette.success.main :
              gameData.status === 'in-progress' ? theme.palette.warning.main :
              theme.palette.divider;
            const accent = winner
              ? curatedVillageColor(winnerColor || '#888888')
              : statusAccent;
            const go = () =>
              navigate(selectedYear ? `/${selectedYear}/giochi/${gameId}` : `/giochi/${gameId}`);

            return (
              <Card
                key={gameId}
                onClick={go}
                sx={{
                  cursor: 'pointer',
                  display: 'flex',
                  flexDirection: 'column',
                  borderLeft: `3px solid ${winnerColor || accent}`,
                  '&:hover': {
                    transform: 'translateY(-3px)',
                    borderColor: 'primary.main',
                    boxShadow: `0 12px 30px ${alpha('#000', 0.45)}`,
                  },
                }}
              >
                <CardContent sx={{ display: 'flex', flexDirection: 'column', gap: 1.25, flex: 1 }}>
                  <Box sx={{ display: 'flex', alignItems: 'flex-start', justifyContent: 'space-between', gap: 1 }}>
                    <Typography variant="h6" component="h2" sx={{ lineHeight: 1.25 }}>
                      {getGameName(gameId)}
                    </Typography>
                    <Chip
                      label={getStatusText(gameData.status)}
                      color={getStatusColor(gameData.status) as any}
                      size="small"
                      sx={{ flexShrink: 0 }}
                    />
                  </Box>

                  {gameData.divisions && gameData.divisions.length > 0 && (
                    <Box sx={{ display: 'flex', flexWrap: 'wrap', gap: 0.75 }}>
                      {(gameData.divisions as any[]).map((division: any, index: number) => (
                        <Chip
                          key={index}
                          label={`${division.name} · ${getStatusText(division.status)}`}
                          color={getStatusColor(division.status) as any}
                          size="small"
                          variant="outlined"
                        />
                      ))}
                    </Box>
                  )}

                  <Box sx={{ flex: 1 }} />

                  <Box sx={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: 1 }}>
                    <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, minWidth: 0 }}>
                      <Typography
                        variant="caption"
                        color="text.secondary"
                        sx={{ textTransform: 'uppercase', letterSpacing: '.08em' }}
                      >
                        Vincitore
                      </Typography>
                      {winner ? (
                        <Box sx={{ display: 'flex', alignItems: 'center', gap: 0.75, minWidth: 0 }}>
                          <VillageToken village={winner} rawColor={winnerColor} size={24} />
                          <Typography variant="body2" fontWeight={700} noWrap>
                            {winner}
                          </Typography>
                        </Box>
                      ) : (
                        <Typography variant="body2" color="text.secondary">
                          —
                        </Typography>
                      )}
                    </Box>
                    <Typography variant="body2" color="primary" sx={{ fontWeight: 600, flexShrink: 0 }}>
                      Dettagli ›
                    </Typography>
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