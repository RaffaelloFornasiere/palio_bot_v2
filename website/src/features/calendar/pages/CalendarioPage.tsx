import React, { useState, useEffect } from 'react';
import { Container, Typography, Box } from '@mui/material';
import { useNavigate } from 'react-router-dom';
import WeeklyCalendar from '../components/WeeklyCalendar';
import { PalioData } from '../../../generated/types.gen';
import { getPalioDataForYear } from '../../../utils/yearApi';
import { useYear } from '../../../contexts/YearContext';
import YearSelector from '../../../components/YearSelector';

const CalendarioPage: React.FC = () => {
  const [events, setEvents] = useState<{ [date: string]: { id: string; title: string; time: string; description?: string; subtitle?: string }[] }>({});
  const { selectedYear } = useYear();

  useEffect(() => {
    // Load palio data from API
    getPalioDataForYear(selectedYear)
      .then(response => {
        if (response.error) {
          throw new Error('Failed to fetch palio data');
        }
        const data = response.data!;
        // Transform the data to match our component's expected format
        const transformedEvents: { [date: string]: { id: string; title: string; time: string; description?: string; subtitle?: string }[] } = {};
        
        // Process games
        data.games.forEach(game => {
          game.dates.forEach((gameDate, dateIndex) => {
            const startDate = new Date(gameDate.start_datetime);
            const endDate = new Date(gameDate.end_datetime);
            
            // Format date as YYYY-MM-DD in local timezone
            const year = startDate.getFullYear();
            const month = String(startDate.getMonth() + 1).padStart(2, '0');
            const day = String(startDate.getDate()).padStart(2, '0');
            const dateString = `${year}-${month}-${day}`;
            
            // Format time
            const startTime = startDate.toLocaleTimeString('it-IT', { 
              hour: '2-digit', 
              minute: '2-digit',
              hour12: false 
            });
            const endTime = endDate.toLocaleTimeString('it-IT', { 
              hour: '2-digit', 
              minute: '2-digit',
              hour12: false 
            });
            
            // For games with multiple dates, use game name as title and subtitle separately
            // For games with single date, use game name as title (no subtitle)
            const eventTitle = game.name;
            const eventSubtitle = game.dates.length > 1 ? gameDate.subtitle || undefined : undefined;
            
            // Initialize array if it doesn't exist
            if (!transformedEvents[dateString]) {
              transformedEvents[dateString] = [];
            }
            
            transformedEvents[dateString].push({
              id: `${game.id}-${dateIndex}`,
              title: eventTitle,
              subtitle: eventSubtitle,
              time: startTime,
              description: `${startTime} - ${endTime}`
            });
          });
        });
        
        // Process non-game events
        data.non_game_events.forEach(event => {
          event.dates.forEach((eventDate, dateIndex) => {
            const startDate = new Date(eventDate.start_datetime);
            const endDate = new Date(eventDate.end_datetime);
            
            // Format date as YYYY-MM-DD in local timezone
            const year = startDate.getFullYear();
            const month = String(startDate.getMonth() + 1).padStart(2, '0');
            const day = String(startDate.getDate()).padStart(2, '0');
            const dateString = `${year}-${month}-${day}`;
            
            // Format time
            const startTime = startDate.toLocaleTimeString('it-IT', { 
              hour: '2-digit', 
              minute: '2-digit',
              hour12: false 
            });
            const endTime = endDate.toLocaleTimeString('it-IT', { 
              hour: '2-digit', 
              minute: '2-digit',
              hour12: false 
            });
            
            // For non-game events, use event name as title and subtitle separately
            const eventTitle = event.name;
            const eventSubtitle = event.dates.length > 1 ? eventDate.subtitle || undefined : undefined;
            
            // Initialize array if it doesn't exist
            if (!transformedEvents[dateString]) {
              transformedEvents[dateString] = [];
            }
            
            transformedEvents[dateString].push({
              id: `${event.name}-${dateIndex}`,
              title: eventTitle,
              subtitle: eventSubtitle,
              time: startTime,
              description: `${startTime} - ${endTime}`
            });
          });
        });
        
        setEvents(transformedEvents);
      })
      .catch(error => {
        console.error('Error loading calendar data:', error);
      });
  }, [selectedYear]);

  return (
    <Box sx={{ height: '100%', display: 'flex', flexDirection: 'column' }}>
      <Box sx={{ p: 2, display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
        <Typography variant="h4" component="h1">
          Calendario Eventi
        </Typography>
        <YearSelector />
      </Box>
      <WeeklyCalendar events={events} />
    </Box>
  );
};

export default CalendarioPage;