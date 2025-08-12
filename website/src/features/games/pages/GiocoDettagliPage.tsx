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
  Divider,
  useTheme
} from '@mui/material';
import { useParams, useNavigate } from 'react-router-dom';
import { ArrowBack } from '@mui/icons-material';
import {
  getPalioGamesStatusForYear,
  getLeaderboardDataForYear,
  getPalioDataForYear
} from '../../../utils/yearApi';
import {
  PalioGamesStatus,
  PalioData,
  Leaderboard,
  LeaderboardEntry,
  ScoreBasedGameStatus,
  RoundRobinGameStatus,
  ScoreBasedDivision,
  RoundRobinDivision,
  GameRound,
  GamePenalty,
  GameBonus,
  ScorePenalty,
  RoundRobinScore
} from '../../../generated';
import { useYear } from '../../../contexts/YearContext';
import { getStatusText, formatDate, getStatusColor } from '../utils';
import { getVillageBackgroundColor } from '../../../utils/colorUtils';


type GameData = ScoreBasedGameStatus | RoundRobinGameStatus;
type GameDivision = ScoreBasedDivision | RoundRobinDivision;
type GameScore = { [key: string]: number | string };

const GiocoDettagliPage: React.FC = () => {
  const { gameId } = useParams<{ gameId: string }>();
  const navigate = useNavigate();
  const { selectedYear } = useYear();
  const theme = useTheme();
  const [gamesData, setGamesData] = useState<PalioGamesStatus | null>(null);
  const [leaderboardData, setLeaderboardData] = useState<Leaderboard | null>(null);
  const [palioData, setPalioData] = useState<PalioData | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

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
    return Object.entries(overallLeaderboard).find(i => i[1].position === 1)?.[0] ?? '-'
  };

  const getVillageColor = (village: string): string | undefined => {
    return palioData?.villages_colors?.[village];
  };

  const getRowBackgroundColor = (village: string, isWinner: boolean = false): string | undefined => {
    const villageColor = getVillageColor(village);
    if (!villageColor) return undefined;
    
    // Get the current theme background color
    const backgroundColor = theme.palette.mode === 'dark' ? '#121212' : '#ffffff';
    // Use stronger opacity for winners, lighter for regular rows
    return getVillageBackgroundColor(villageColor, backgroundColor, 0.4);
  };

  const toEntries = (scores: GameScore | RoundRobinScore[]): [string, number | string][] => {
    if (Array.isArray(scores)) {
      // Handle RoundRobinScore[] format
      return scores.map(score => [score.village, score.points]);
    }
    // Handle object format
    return Object.entries(scores);
  };

  const getSortedLeaderboard = (leaderboard: { [key: string]: number | number }): [string, number][] => {
    return Object.entries(leaderboard).sort(([, a], [, b]) => (b as number) - (a as number));
  };

  // Helper functions to extract game data
  const getGameRounds = (gameData: GameData): GameRound[] => {
    return (gameData as RoundRobinGameStatus).rounds || [];
  };

  const getGameScores = (gameData: GameData): GameScore | null => {
    if ('scores' in gameData && gameData.scores) {
      return gameData.scores;
    }
    return null;
  };

  const hasGameDivisions = (gameData: GameData): boolean => {
    return (gameData.divisions?.length ?? 0) > 0;
  };

  const getDivisionRounds = (division: any): GameRound[] => {
    return division.rounds || [];
  };

  const getDivisionScores = (division: any): GameScore | null => {
    return division.scores || null;
  };

  const renderPenaltiesAndBonuses = (
    scorePenalties?: ScorePenalty[],
    appliedPenalties?: GamePenalty[],
    appliedBonuses?: GameBonus[]
  ) => {
    const hasAny = (scorePenalties && scorePenalties.length > 0) ||
                   (appliedPenalties && appliedPenalties.length > 0) ||
                   (appliedBonuses && appliedBonuses.length > 0);

    if (!hasAny) return null;

    return (
      <Box sx={{ mb: 2 }}>
        <Typography variant="body2" color="text.secondary" gutterBottom>
          <strong>Penalità e Bonus</strong>
        </Typography>

        {scorePenalties && scorePenalties.length > 0 && (
          <Box sx={{ mb: 1 }}>
            <Typography variant="body2" color="error.main" gutterBottom>
              Penalità Punteggio:
            </Typography>
            {scorePenalties.map((penalty, index) => (
              <Box key={index} sx={{ ml: 2, mb: 0.5 }}>
                <Typography variant="body2" color="text.secondary">
                  • {penalty.village}: {penalty.description} ({penalty.points} punti)
                </Typography>
              </Box>
            ))}
          </Box>
        )}

        {appliedPenalties && appliedPenalties.length > 0 && (
          <Box sx={{ mb: 1 }}>
            <Typography variant="body2" color="error.main" gutterBottom>
              Penalità Classifica:
            </Typography>
            {appliedPenalties.map((penalty, index) => (
              <Box key={index} sx={{ ml: 2, mb: 0.5 }}>
                <Typography variant="body2" color="text.secondary">
                  • {penalty.village}: {penalty.description} ({penalty.points} punti)
                </Typography>
              </Box>
            ))}
          </Box>
        )}

        {appliedBonuses && appliedBonuses.length > 0 && (
          <Box sx={{ mb: 1 }}>
            <Typography variant="body2" color="success.main" gutterBottom>
              Bonus Classifica:
            </Typography>
            {appliedBonuses.map((bonus, index) => (
              <Box key={index} sx={{ ml: 2, mb: 0.5 }}>
                <Typography variant="body2" color="text.secondary">
                  • {bonus.village}: {bonus.description} (+{bonus.points} punti)
                </Typography>
              </Box>
            ))}
          </Box>
        )}
      </Box>
    );
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
  console.log(gamesData)
  const gameLeaderboard = leaderboardData?.game_leaderboards[gameId];

  return (
    <Container maxWidth="lg">
      <Box sx={{ mt: 4, mb: 4 }}>
        <Box sx={{ mb: 3 }}>
          <Button
            startIcon={<ArrowBack />}
            onClick={() => navigate(selectedYear ? `/${selectedYear}/giochi` : '/giochi')}
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
          {/* Game Status and Winner - adjust grid columns based on divisions */}
          <Box
             sx={{
            display: 'grid', 
            gridTemplateColumns: { 
              xs: '1fr', 
              md: '1fr 1fr'
            }, 
            gap: 3 
          }}>
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
                    <strong>Vincitore:</strong> {getWinner(gameId)}
                  </Typography>
                </Box>

                {/* Game-level penalties and bonuses */}
                {renderPenaltiesAndBonuses(
                  'score_penalties' in gameData ? gameData.score_penalties : undefined,
                  'applied_penalties' in gameData ? gameData.applied_penalties : undefined,
                  'applied_bonuses' in gameData ? gameData.applied_bonuses : undefined
                )}
              </CardContent>
            </Card>

            {/* Game Leaderboard Points - always show on right if available */}
            {gameLeaderboard && (
              <Card>
                <CardContent>
                  <Typography variant="h6" gutterBottom>
                    Classifica Generale
                  </Typography>

                  <TableContainer>
                    <Table size="small">
                      <TableHead>
                        <TableRow>
                          <TableCell>Pos</TableCell>
                          <TableCell>Borgo</TableCell>
                          <TableCell align="right">Punti</TableCell>
                        </TableRow>
                      </TableHead>
                      <TableBody>
                        {Object.entries(gameLeaderboard.overall_leaderboard)
                          .sort(([,a], [,b]) => a.position - b.position)
                          .map(([village, entry]) => (
                          <TableRow 
                            key={village}
                            sx={{ 
                              backgroundColor: getRowBackgroundColor(village, entry.position === 1),
                              transition: 'background-color 0.2s'
                            }}
                          >
                            <TableCell>{entry.position}</TableCell>
                            <TableCell>{village}</TableCell>
                            <TableCell align="right">{entry.points}</TableCell>
                          </TableRow>
                        ))}
                      </TableBody>
                    </Table>
                  </TableContainer>
                </CardContent>
              </Card>
            )}
          </Box>
          {/* Divisions - Show each division in its own card */}
          {hasGameDivisions(gameData) && (

            <Box sx={{ display: 'flex', flexDirection: 'column', gap: 3 }}>
              {gameData.divisions!.map((division: any, divIndex: number) => {
                const divisionRounds = getDivisionRounds(division);
                const divisionScores = getDivisionScores(division);
                
                return (
                  <Card key={divIndex}>
                    <CardContent>
                      <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, mb: 3 }}>
                        <Typography variant="h6" fontWeight="medium">
                          {division.name}
                        </Typography>
                        <Chip
                          label={getStatusText(division.status)}
                          color={getStatusColor(division.status) as any}
                          size="small"
                        />
                      </Box>

                      {/* Division-level penalties and bonuses */}
                      {renderPenaltiesAndBonuses(
                        'score_penalties' in division ? division.score_penalties : undefined,
                        'applied_penalties' in division ? division.applied_penalties : undefined,
                        'applied_bonuses' in division ? division.applied_bonuses : undefined
                      )}

                      {/* Division Rounds */}
                      {divisionRounds.length > 0 && (
                        <Box sx={{ mb: 3 }}>
                          <Typography variant="body1" fontWeight="medium" gutterBottom>
                            Rounds
                          </Typography>
                          {divisionRounds.map((round: any, roundIndex: number) => (
                            <Box key={roundIndex} sx={{ mb: 2 }}>
                              <Typography variant="body2" sx={{ mb: 1 }}>
                                Round {roundIndex + 1}
                              </Typography>
                              <TableContainer component={Paper} variant="outlined">
                                <Table size="small">
                                  <TableHead>
                                    <TableRow>
                                      <TableCell>Borgo</TableCell>
                                      <TableCell align="right">Punteggio</TableCell>
                                    </TableRow>
                                  </TableHead>
                                  <TableBody>
                                    {toEntries(round.scores || []).map(([village, score], index) => (
                                      <TableRow 
                                        key={village}
                                        sx={{ 
                                          backgroundColor: getRowBackgroundColor(village, false),
                                          transition: 'background-color 0.2s'
                                        }}
                                      >
                                        <TableCell>{village}</TableCell>
                                        <TableCell align="right">{score}</TableCell>
                                      </TableRow>
                                    ))}
                                  </TableBody>
                                </Table>
                              </TableContainer>

                              {/* Round-level penalties */}
                              {round.score_penalties && round.score_penalties.length > 0 &&
                                renderPenaltiesAndBonuses(round.score_penalties, undefined, undefined)
                              }
                            </Box>
                          ))}
                        </Box>
                      )}

                      {/* Division Leaderboard - Show if available in gameLeaderboard */}
                      {gameLeaderboard?.divisions && gameLeaderboard.divisions.length > 0 && (
                        (() => {
                          const divisionLeaderboard = gameLeaderboard.divisions.find(
                            (d: any) => d.name === division.name
                          );
                          
                          if (!divisionLeaderboard) return null;
                          
                          return (
                            <Box sx={{ mb: 3 }}>
                              <Typography variant="body1" fontWeight="medium" gutterBottom>
                                Classifica {division.name}
                              </Typography>
                              <TableContainer component={Paper} variant="outlined">
                                <Table size="small">
                                  <TableHead>
                                    <TableRow>
                                      <TableCell>Pos.</TableCell>
                                      <TableCell>Borgo</TableCell>
                                      <TableCell align="right">Punti</TableCell>
                                    </TableRow>
                                  </TableHead>
                                  <TableBody>
                                    {Object.entries(divisionLeaderboard.leaderboard)
                                      .sort(([,a], [,b]) => {
                                        const entryA = a as LeaderboardEntry;
                                        const entryB = b as LeaderboardEntry;
                                        return entryA.position - entryB.position;
                                      })
                                      .map(([village, entry]) => {
                                        const leaderboardEntry = entry as LeaderboardEntry;
                                        return (
                                          <TableRow 
                                            key={village}
                                            sx={{ 
                                              backgroundColor: getRowBackgroundColor(village, leaderboardEntry.position === 1),
                                              transition: 'background-color 0.2s'
                                            }}
                                          >
                                            <TableCell>{leaderboardEntry.position}</TableCell>
                                            <TableCell>{village}</TableCell>
                                            <TableCell align="right">
                                              {leaderboardEntry.points}
                                            </TableCell>
                                          </TableRow>
                                        );
                                      })}
                                  </TableBody>
                                </Table>
                              </TableContainer>
                            </Box>
                          );
                        })()
                      )}

                      {/* Division Final Scores Table */}
                      {divisionScores && Object.keys(divisionScores).length > 0 && (
                        <Box>
                          <Typography variant="body1" fontWeight="medium" gutterBottom>
                            Risultati
                          </Typography>
                          <TableContainer component={Paper} variant="outlined">
                            <Table size="small">
                              <TableHead>
                                <TableRow>
                                  <TableCell>Borgo</TableCell>
                                  <TableCell align="right">Punteggio</TableCell>
                                </TableRow>
                              </TableHead>
                              <TableBody>
                                {toEntries(divisionScores).map(([village, score], index) => (
                                  <TableRow 
                                    key={village}
                                    sx={{ 
                                      backgroundColor: getRowBackgroundColor(village, index === 0),
                                      transition: 'background-color 0.2s'
                                    }}
                                  >
                                    <TableCell>{village}</TableCell>
                                    <TableCell align="right">{score}</TableCell>
                                  </TableRow>
                                ))}
                              </TableBody>
                            </Table>
                          </TableContainer>
                        </Box>
                      )}
                    </CardContent>
                  </Card>
                );
              })}
            </Box>
          )}

          {/* Game Scores - Only show if there are no divisions */}
          {(() => {
            const gameScores = getGameScores(gameData);
            return gameScores && !hasGameDivisions(gameData) && (
              <Card>
                <CardContent>
                  <Typography variant="h6" gutterBottom>
                    Risultati
                  </Typography>

                  <TableContainer component={Paper} variant="outlined">
                    <Table>
                      <TableHead>
                        <TableRow>
                          <TableCell>Borgo</TableCell>
                          <TableCell align="right">Punteggio</TableCell>
                        </TableRow>
                      </TableHead>
                      <TableBody>
                        {toEntries(gameScores).map(([village, score], index) => (
                          <TableRow 
                            key={village}
                            sx={{ 
                              backgroundColor: getRowBackgroundColor(village, index === 0),
                              transition: 'background-color 0.2s'
                            }}
                          >
                            <TableCell>
                              <Typography variant="body1">
                                {village}
                              </Typography>
                            </TableCell>
                            <TableCell align="right">
                              <Typography variant="body1">
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
            );
          })()}

          {/* Rounds (for in-progress games) - Only show if there are no divisions */}
          {(() => {
            const gameRounds = getGameRounds(gameData);
            return gameRounds.length > 0 && !hasGameDivisions(gameData) && (
              <Card>
                <CardContent>
                  <Typography variant="h6" gutterBottom>
                    Punteggi per Round
                  </Typography>

                  {gameRounds.map((round: any, index: number) => (
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
                            {toEntries(round.scores || []).map(([village, score], index) => (
                              <TableRow 
                                key={village}
                                sx={{ 
                                  backgroundColor: getRowBackgroundColor(village, false),
                                  transition: 'background-color 0.2s'
                                }}
                              >
                                <TableCell>{village}</TableCell>
                                <TableCell align="right">{score}</TableCell>
                              </TableRow>
                            ))}
                          </TableBody>
                        </Table>
                      </TableContainer>

                      {/* Round-level penalties */}
                      {round.score_penalties && round.score_penalties.length > 0 &&
                        renderPenaltiesAndBonuses(round.score_penalties, undefined, undefined)
                      }

                      {index < gameRounds.length - 1 && <Divider />}
                    </Box>
                  ))}
                </CardContent>
              </Card>
            );
          })()}

        </Box>
      </Box>
    </Container>
  );
};

export default GiocoDettagliPage;