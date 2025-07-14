import React, { useState } from 'react';
import { Box, Typography, Paper, IconButton, useTheme, useMediaQuery, Divider } from '@mui/material';
import { ChevronLeft, ChevronRight } from '@mui/icons-material';

interface Event {
  id: string;
  title: string;
  time: string;
  description?: string;
}

interface WeeklyCalendarProps {
  events?: { [date: string]: Event[] };
}

const WeeklyCalendar: React.FC<WeeklyCalendarProps> = ({ events = {} }) => {
  const [currentWeek, setCurrentWeek] = useState(new Date());
  const theme = useTheme();
  const isMobile = useMediaQuery(theme.breakpoints.down('md'));

  const weekdays = isMobile 
    ? ['L', 'M', 'M', 'G', 'V', 'S', 'D']
    : ['Lunedì', 'Martedì', 'Mercoledì', 'Giovedì', 'Venerdì', 'Sabato', 'Domenica'];

  const getWeekDates = (date: Date) => {
    const startOfWeek = new Date(date);
    const day = startOfWeek.getDay();
    const diff = startOfWeek.getDate() - day + (day === 0 ? -6 : 1);
    startOfWeek.setDate(diff);

    const weekDates = [];
    for (let i = 0; i < 7; i++) {
      const date = new Date(startOfWeek);
      date.setDate(startOfWeek.getDate() + i);
      weekDates.push(date);
    }
    return weekDates;
  };

  const formatDate = (date: Date) => {
    return date.toISOString().split('T')[0];
  };

  const formatDisplayDate = (date: Date) => {
    return date.getDate().toString();
  };

  const weekDates = getWeekDates(currentWeek);

  // Helper function to get all events for a week sorted by date and time
  const getWeekEvents = (dates: Date[]) => {
    const weekEvents: { date: Date, events: Event[] }[] = [];
    
    dates.forEach(date => {
      const dateStr = formatDate(date);
      const dayEvents = events[dateStr] || [];
      
      if (dayEvents.length > 0) {
        weekEvents.push({
          date,
          events: dayEvents.sort((a, b) => a.time.localeCompare(b.time))
        });
      }
    });
    
    return weekEvents;
  };

  const currentWeekEvents = getWeekEvents(weekDates);

  const goToPreviousWeek = () => {
    const newDate = new Date(currentWeek);
    newDate.setDate(currentWeek.getDate() - 7);
    setCurrentWeek(newDate);
  };

  const goToNextWeek = () => {
    const newDate = new Date(currentWeek);
    newDate.setDate(currentWeek.getDate() + 7);
    setCurrentWeek(newDate);
  };

  return (
    <Box sx={{ 
      width: '100vw', 
      height: '100vh',
      maxWidth: isMobile ? '100vw' : 1200, 
      mx: 'auto', 
      px: 0,
      display: 'flex',
      flexDirection: 'column',
      overflow: 'hidden'
    }}>
      {/* Header with navigation */}
      <Box sx={{ 
        display: 'flex', 
        alignItems: 'center', 
        justifyContent: 'space-between', 
        p: isMobile ? 2 : 3,
        flexShrink: 0
      }}>
        <IconButton onClick={goToPreviousWeek} size={isMobile ? "medium" : "large"}>
          <ChevronLeft />
        </IconButton>
        <Typography variant={isMobile ? "h6" : "h5"} component="h2">
          {weekDates[0].toLocaleDateString('it-IT', { month: 'long', year: 'numeric' })}
        </Typography>
        <IconButton onClick={goToNextWeek} size={isMobile ? "medium" : "large"}>
          <ChevronRight />
        </IconButton>
      </Box>

      {/* Week view */}
      <Box
        sx={{
          display: 'flex',
          flexDirection: 'column',
          flex: 1,
          overflow: 'hidden',
          minHeight: 0
        }}
      >
        {/* Week headers */}
        <Box
          sx={{
            display: 'flex',
            borderBottom: 1,
            borderColor: 'divider',
            flexShrink: 0
          }}
        >
          {weekdays.map((day, index) => (
            <Box
              key={`${day}-${index}`}
              sx={{
                flex: 1,
                p: isMobile ? 0.5 : 2,
                textAlign: 'center',
                borderRight: index < 6 ? 1 : 0,
                borderColor: 'divider',
                minWidth: 0
              }}
            >
              <Typography variant={isMobile ? "caption" : "subtitle1"} fontWeight="bold" noWrap>
                {day}
              </Typography>
              <Typography variant={isMobile ? "body2" : "h6"} color="primary" noWrap>
                {formatDisplayDate(weekDates[index])}
              </Typography>
            </Box>
          ))}
        </Box>

        {/* Events list */}
        <Box
          sx={{
            flex: 1,
            overflow: 'auto',
            p: isMobile ? 1 : 2,
            '&::-webkit-scrollbar': { display: 'none' },
            msOverflowStyle: 'none',
            scrollbarWidth: 'none'
          }}
        >
          {currentWeekEvents.length === 0 ? (
            <Typography variant="body2" color="text.secondary" sx={{ textAlign: 'center', mt: 4 }}>
              Nessun evento questa settimana
            </Typography>
          ) : (
            currentWeekEvents.map(({ date, events: dayEvents }) => (
              <Box key={formatDate(date)} sx={{ mb: 3 }}>
                <Typography variant="h6" sx={{ mb: 2, color: 'primary.main' }}>
                  {date.toLocaleDateString('it-IT', { weekday: 'long', day: 'numeric', month: 'long' })}
                </Typography>
                {dayEvents.map((event) => (
                  <Paper
                    key={event.id}
                    sx={{
                      p: isMobile ? 1.5 : 2,
                      mb: 1,
                      backgroundColor: 'primary.light',
                      color: 'primary.contrastText',
                      cursor: 'pointer',
                      '&:hover': {
                        backgroundColor: 'primary.main',
                        boxShadow: 4
                      }
                    }}
                  >
                    <Box sx={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', mb: 1 }}>
                      <Typography variant={isMobile ? "body1" : "h6"} fontWeight="bold">
                        {event.title}
                      </Typography>
                      <Typography variant="body2" sx={{ opacity: 0.9 }}>
                        {event.time}
                      </Typography>
                    </Box>
                    {event.description && (
                      <Typography variant="body2" sx={{ opacity: 0.8 }}>
                        {event.description}
                      </Typography>
                    )}
                  </Paper>
                ))}
                <Divider sx={{ mt: 2 }} />
              </Box>
            ))
          )}
        </Box>
      </Box>
    </Box>
  );
};

export default WeeklyCalendar;