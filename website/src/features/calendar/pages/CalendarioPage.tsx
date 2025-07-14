import React from 'react';
import { Container, Typography, Box } from '@mui/material';
import WeeklyCalendar from '../components/WeeklyCalendar';

const CalendarioPage: React.FC = () => {
  // Sample events data - replace with actual data source
  const sampleEvents = {
    '2025-07-13': [
      { id: '1', title: 'Riunione Team', time: '09:00', description: 'Riunione settimanale' },
      { id: '2', title: 'Pranzo', time: '12:30' }
    ],
    '2025-07-15': [
      { id: '3', title: 'Workshop', time: '14:00', description: 'Workshop di formazione' }
    ],
    '2025-07-17': [
      { id: '4', title: 'Evento Palio', time: '18:00', description: 'Preparazione evento' },
      { id: '5', title: 'Cena', time: '20:00' }
    ]
  };

  return (
    <Container maxWidth="xl">
      <Box sx={{ mt: 4, mb: 4 }}>
        <Typography variant="h4" component="h1" gutterBottom>
          Calendario
        </Typography>
        <WeeklyCalendar events={sampleEvents} />
      </Box>
    </Container>
  );
};

export default CalendarioPage;