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
          const day = parseInt(dayNumber);
          
          // Create a date for August 2025
          // We need to find the correct date that matches both the day number AND the day name
          let date = new Date(2025, 7, day); // August 2025 (month is 0-indexed)
          
          // Map day names to JavaScript day numbers (0 = Sunday, 1 = Monday, etc.)
          const dayNameMap: { [key: string]: number } = {
            'Sunday': 0,
            'Monday': 1,
            'Tuesday': 2,
            'Wednesday': 3,
            'Thursday': 4,
            'Friday': 5,
            'Saturday': 6
          };
          
          // Check if the created date matches the expected day of week
          const expectedDayOfWeek = dayNameMap[dayName];
          const actualDayOfWeek = date.getDay();
          
          // If they don't match, adjust the date
          if (expectedDayOfWeek !== actualDayOfWeek) {
            // This might happen if the day number doesn't align with the day name in August 2025
            console.warn(`Date mismatch: ${dayKey} doesn't align properly in August 2025`);
          }
          
          // Format date as YYYY-MM-DD in local timezone
          const year = date.getFullYear();
          const month = String(date.getMonth() + 1).padStart(2, '0');
          const dayStr = String(date.getDate()).padStart(2, '0');
          const dateString = `${year}-${month}-${dayStr}`;
          
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
    <Box sx={{ height: '100%', display: 'flex', flexDirection: 'column' }}>
      <WeeklyCalendar events={events} />
    </Box>
  );
};

export default CalendarioPage;