import React, { useState, useEffect } from 'react';
import { 
  Container, 
  Typography, 
  Box, 
  Table,
  TableBody,
  TableCell,
  TableContainer,
  TableHead,
  TableRow,
  Paper,
  Card,
  CardContent,
  CircularProgress,
  Alert,
  Chip
} from '@mui/material';
import { getLeaderboardData } from '../../../generated/sdk.gen';
import { Leaderboard } from '../../../generated/types.gen';

interface VillagePoints {
  [village: string]: number;
}

interface LeaderboardEntry {
  village: string;
  points: number;
  position: number;
  gap?: number;
}

const ClassificaPage: React.FC = () => {
  const [leaderboardData, setLeaderboardData] = useState<Leaderboard | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const fetchData = async () => {
      try {
        setLoading(true);
        const response = await getLeaderboardData();

        if (response.error) {
          throw new Error('Failed to fetch leaderboard data');
        }

        setLeaderboardData(response.data!);
      } catch (err) {
        setError(err instanceof Error ? err.message : 'An error occurred');
      } finally {
        setLoading(false);
      }
    };

    fetchData();
  }, []);

  const getLeaderboardEntries = (): LeaderboardEntry[] => {
    if (!leaderboardData) return [];

    // Sort villages by points (descending)
    const sortedEntries = Object.entries(leaderboardData.points)
      .sort(([, a], [, b]) => b - a)
      .map(([village, points], index) => ({
        village,
        points,
        position: index + 1,
      }));

    // Calculate gap to next position for villages from 2nd position onwards
    const entriesWithGaps: LeaderboardEntry[] = sortedEntries.map((entry, index) => {
      if (index === 0) {
        // First place doesn't need gap calculation
        return entry;
      }
      
      const nextPositionPoints = sortedEntries[index - 1].points;
      const gap = nextPositionPoints - entry.points;
      
      return {
        ...entry,
        gap,
      };
    });

    return entriesWithGaps;
  };

  const getPositionColor = (position: number) => {
    switch (position) {
      case 1:
        return 'gold';
      case 2:
        return 'silver';
      case 3:
        return '#CD7F32'; // Bronze
      default:
        return 'default';
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
            Errore nel caricamento della classifica: {error}
          </Alert>
        </Box>
      </Container>
    );
  }

  const leaderboardEntries = getLeaderboardEntries();

  return (
    <Container maxWidth="lg" >
      <Box sx={{ mt: 4, mb: 4}}>
        <Typography variant="h4" component="h1" gutterBottom>
          Classifica Generale
        </Typography>
        
        <Card >
          <CardContent sx={{p:0}}>
            <TableContainer component={Paper} variant="outlined">
              <Table size="small">
                <TableHead>
                  <TableRow>
                    <TableCell ></TableCell>
                    <TableCell >Borgo</TableCell>
                    <TableCell  align="right">Punti Totali</TableCell>
                    <TableCell  align="right">Distacco</TableCell>
                  </TableRow>
                </TableHead>
                <TableBody>
                  {leaderboardEntries.map((entry) => (
                    <TableRow key={entry.village}>
                      <TableCell>
                        <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
                          <Typography
                            variant="h6"
                            fontWeight={entry.position <= 3 ? 'bold' : 'normal'}
                          >
                            {entry.position.toString()}
                          </Typography>
                        </Box>
                      </TableCell>
                      <TableCell>
                        <Typography 
                          variant="body1" 
                          fontWeight={entry.position === 1 ? 'bold' : 'normal'}
                        >
                          {entry.village}
                        </Typography>
                      </TableCell>
                      <TableCell align="right">
                        <Typography 
                          variant="body1" 
                          fontWeight={entry.position === 1 ? 'bold' : 'normal'}
                        >
                          {entry.points}
                        </Typography>
                      </TableCell>
                      <TableCell align="right">
                        {entry.gap !== undefined ? (
                          <Box sx={{ display: 'flex', alignItems: 'center', justifyContent: 'flex-end', gap: 1 }}>
                            <Typography variant="body2" color="error">
                              -{entry.gap}
                            </Typography>
                          </Box>
                        ) : (
                          entry.points > 0 ? (
                            <Typography variant="body2" color="success.main" fontWeight="bold">
                              🏆
                            </Typography>
                          ) : (
                            <Typography variant="body2" color="text.secondary">
                              -
                            </Typography>
                          )
                        )}
                      </TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            </TableContainer>
          </CardContent>
        </Card>

        {leaderboardEntries.length === 0 && (
          <Box sx={{ mt: 4, textAlign: 'center' }}>
            <Typography variant="body1" color="text.secondary">
              Nessun dato disponibile per la classifica.
            </Typography>
          </Box>
        )}
      </Box>
    </Container>
  );
};

export default ClassificaPage;