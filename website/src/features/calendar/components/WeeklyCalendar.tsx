import React, { useState, useRef } from 'react';
import { Box, Typography, Paper, IconButton, useTheme, useMediaQuery, Divider, Fade } from '@mui/material';
import { ChevronLeft, ChevronRight } from '@mui/icons-material';
import AnimatedBox from './AnimatedBox';

interface Event {
  id: string;
  title: string;
  time: string;
  description?: string;
  subtitle?: string;
}

interface WeeklyCalendarProps {
  events?: { [date: string]: Event[] };
}

const WeeklyCalendar: React.FC<WeeklyCalendarProps> = ({ events = {} }) => {
  const [currentWeek, setCurrentWeek] = useState(new Date());
  const [animationDirection, setAnimationDirection] = useState<'left' | 'right'>('left');
  const [isTransitioning, setIsTransitioning] = useState(false);
  const theme = useTheme();
  const isMobile = useMediaQuery(theme.breakpoints.down('md'));
  
  // Touch tracking refs for swipe gesture
  const touchStartX = useRef<number>(0);
  const touchEndX = useRef<number>(0);
  const minSwipeDistance = 50; // Minimum distance for swipe to register

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
    // Format date as YYYY-MM-DD in local timezone to avoid timezone issues
    const year = date.getFullYear();
    const month = String(date.getMonth() + 1).padStart(2, '0');
    const day = String(date.getDate()).padStart(2, '0');
    return `${year}-${month}-${day}`;
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
    setAnimationDirection('left');
    setIsTransitioning(true);
    setTimeout(() => {
      const newDate = new Date(currentWeek);
      newDate.setDate(currentWeek.getDate() - 7);
      setCurrentWeek(newDate);
      setIsTransitioning(false);
    }, 50);
  };

  const goToNextWeek = () => {
    setAnimationDirection('right');
    setIsTransitioning(true);
    setTimeout(() => {
      const newDate = new Date(currentWeek);
      newDate.setDate(currentWeek.getDate() + 7);
      setCurrentWeek(newDate);
      setIsTransitioning(false);
    }, 50);
  };

  // Touch event handlers for swipe gesture
  const handleTouchStart = (e: React.TouchEvent) => {
    touchStartX.current = e.touches[0].clientX;
  };

  const handleTouchMove = (e: React.TouchEvent) => {
    touchEndX.current = e.touches[0].clientX;
  };

  const handleTouchEnd = () => {
    if (!touchStartX.current || !touchEndX.current) return;
    
    const distance = touchStartX.current - touchEndX.current;
    const isLeftSwipe = distance > minSwipeDistance;
    const isRightSwipe = distance < -minSwipeDistance;

    if (isLeftSwipe && isMobile) {
      goToNextWeek();
    }
    if (isRightSwipe && isMobile) {
      goToPreviousWeek();
    }
  };

  return (
    <Box 
      sx={{ 
        width: '100vw', 
        height: { xs: 'calc(100vh - 64px)', md: '100vh' }, // Subtract AppBar height on mobile
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
        <AnimatedBox
          animationKey={currentWeek.getTime()}
          direction={animationDirection}
          duration={0.3}
          sx={{
            display: 'flex',
            borderBottom: 1,
            borderColor: 'divider',
            flexShrink: 0
          }}
          onTouchStart={handleTouchStart}
          onTouchMove={handleTouchMove}
          onTouchEnd={handleTouchEnd}
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
        </AnimatedBox>

        {/* Events list */}
        <Box
          sx={{
            flex: 1,
            overflow: 'auto',
            p: isMobile ? 1 : 2,
            '&::-webkit-scrollbar': { display: 'none' },
            msOverflowStyle: 'none',
            scrollbarWidth: 'none',
            position: 'relative'
          }}
        >
          <Fade in={!isTransitioning} timeout={500}>
            <Box>
              {currentWeekEvents.length === 0 ? (
                <Typography variant="body2" color="text.secondary" sx={{ textAlign: 'center', mt: 4 }}>
                  Nessun evento questa settimana
                </Typography>
              ) : (
                currentWeekEvents.map(({ date, events: dayEvents }, dayIndex) => (
                  <Fade key={formatDate(date)} in={!isTransitioning} timeout={300 + dayIndex * 100}>
                    <Box sx={{ mb: 3 }}>
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
                    {event.subtitle && (
                      <Typography variant="body2" sx={{ opacity: 0.9, mb: 1, fontStyle: 'italic' }}>
                        {event.subtitle}
                      </Typography>
                    )}
                    {event.description && (
                      <Typography variant="body2" sx={{ opacity: 0.8 }}>
                        {event.description}
                      </Typography>
                    )}
                      </Paper>
                    ))}
                    <Divider sx={{ mt: 2 }} />
                  </Box>
                </Fade>
              ))
            )}
          </Box>
        </Fade>
      </Box>
      </Box>
    </Box>
  );
};

export default WeeklyCalendar;