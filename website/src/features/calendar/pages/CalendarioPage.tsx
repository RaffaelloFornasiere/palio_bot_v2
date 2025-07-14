import React, { useState, useEffect } from 'react';
import { Container, Typography, Box } from '@mui/material';
import WeeklyCalendar from '../components/WeeklyCalendar';

interface CalendarEvent {
  event: string;
  startTime: string;
  endTime: string;
}

interface CalendarData {
  [key: string]: CalendarEvent[];
}

const CalendarioPage: React.FC = () => {
  const [events, setEvents] = useState<{ [date: string]: { id: string; title: string; time: string; description?: string }[] }>({});

  useEffect(() => {
    // Load calendar.json from public folder
    fetch('/calendar.json')
      .then(response => response.json())
      .then((data: CalendarData) => {
        // Transform the data to match our component's expected format
        const transformedEvents: { [date: string]: { id: string; title: string; time: string; description?: string }[] } = {};
        
        Object.entries(data).forEach(([dayKey, dayEvents]) => {
          // Parse the day key (e.g., "Friday, 1" -> August 1st, 2025)
          const [dayName, dayNumber] = dayKey.split(', ');
          const date = new Date(2025, 7, parseInt(dayNumber)); // August 2025 (month is 0-indexed)
          const dateString = date.toISOString().split('T')[0];
          
          transformedEvents[dateString] = dayEvents.map((event, index) => ({
            id: `${dateString}-${index}`,
            title: event.event,
            time: event.startTime,
            description: `${event.startTime} - ${event.endTime}`
          }));
        });
        
        setEvents(transformedEvents);
      })
      .catch(error => {
        console.error('Error loading calendar data:', error);
      });
  }, []);

  return (
    <Box sx={{ height: '100vh', display: 'flex', flexDirection: 'column' }}>
      <WeeklyCalendar events={events} />
    </Box>
  );
};

export default CalendarioPage;