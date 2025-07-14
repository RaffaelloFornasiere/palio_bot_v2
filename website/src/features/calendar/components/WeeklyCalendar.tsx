import React, { useState, useRef, useEffect } from 'react';
import { Box, Typography, Paper, IconButton, useTheme, useMediaQuery } from '@mui/material';
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
  const [translateX, setTranslateX] = useState(0);
  const [isAnimating, setIsAnimating] = useState(false);
  const scrollRef = useRef<HTMLDivElement>(null);
  const containerRef = useRef<HTMLDivElement>(null);
  const theme = useTheme();
  const isMobile = useMediaQuery(theme.breakpoints.down('md'));

  // Helper function to get adjacent weeks
  const getPreviousWeek = (date: Date) => {
    const prevWeek = new Date(date);
    prevWeek.setDate(date.getDate() - 7);
    return prevWeek;
  };

  const getNextWeek = (date: Date) => {
    const nextWeek = new Date(date);
    nextWeek.setDate(date.getDate() + 7);
    return nextWeek;
  };

  const weekdays = isMobile 
    ? ['Lun', 'Mar', 'Mer', 'Gio', 'Ven', 'Sab', 'Dom']
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
  const prevWeekDates = getWeekDates(getPreviousWeek(currentWeek));
  const nextWeekDates = getWeekDates(getNextWeek(currentWeek));

  const animateToWeek = (direction: 'prev' | 'next') => {
    if (isAnimating) return;
    
    setIsAnimating(true);
    const containerWidth = containerRef.current?.clientWidth || 0;
    const targetTranslateX = direction === 'next' ? -containerWidth : containerWidth;
    
    setTranslateX(targetTranslateX);
    
    setTimeout(() => {
      const newDate = new Date(currentWeek);
      newDate.setDate(currentWeek.getDate() + (direction === 'next' ? 7 : -7));
      setCurrentWeek(newDate);
      setTranslateX(0);
      setIsAnimating(false);
    }, 300);
  };

  const goToPreviousWeek = () => {
    animateToWeek('prev');
  };

  const goToNextWeek = () => {
    animateToWeek('next');
  };

  const handleScroll = (direction: 'left' | 'right') => {
    if (scrollRef.current) {
      const scrollAmount = scrollRef.current.clientWidth;
      scrollRef.current.scrollBy({
        left: direction === 'right' ? scrollAmount : -scrollAmount,
        behavior: 'smooth'
      });
    }
  };

  useEffect(() => {
    const handleWheel = (e: WheelEvent) => {
      if (e.deltaX !== 0) {
        e.preventDefault();
        if (e.deltaX > 0) {
          goToNextWeek();
        } else {
          goToPreviousWeek();
        }
      }
    };

    const handleTouch = (() => {
      let startX = 0;
      let startY = 0;
      let isDragging = false;
      let currentTranslateX = 0;

      const handleTouchStart = (e: TouchEvent) => {
        if (isAnimating) return;
        startX = e.touches[0].clientX;
        startY = e.touches[0].clientY;
        isDragging = false;
        currentTranslateX = 0;
      };

      const handleTouchMove = (e: TouchEvent) => {
        if (isAnimating) return;
        
        const deltaX = e.touches[0].clientX - startX;
        const deltaY = e.touches[0].clientY - startY;
        
        if (!isDragging && Math.abs(deltaX) > Math.abs(deltaY) && Math.abs(deltaX) > 10) {
          isDragging = true;
          e.preventDefault();
        }
        
        if (isDragging) {
          e.preventDefault();
          currentTranslateX = deltaX * 0.5; // Damping factor
          setTranslateX(currentTranslateX);
        }
      };

      const handleTouchEnd = (e: TouchEvent) => {
        if (isAnimating) return;
        
        if (isDragging) {
          const deltaX = e.changedTouches[0].clientX - startX;
          const threshold = 80;
          
          if (Math.abs(deltaX) > threshold) {
            if (deltaX > 0) {
              goToPreviousWeek();
            } else {
              goToNextWeek();
            }
          } else {
            // Snap back
            setTranslateX(0);
          }
        }
        isDragging = false;
      };

      return { handleTouchStart, handleTouchMove, handleTouchEnd };
    })();

    const scrollElement = scrollRef.current;
    if (scrollElement) {
      scrollElement.addEventListener('wheel', handleWheel, { passive: false });
      scrollElement.addEventListener('touchstart', handleTouch.handleTouchStart, { passive: false });
      scrollElement.addEventListener('touchmove', handleTouch.handleTouchMove, { passive: false });
      scrollElement.addEventListener('touchend', handleTouch.handleTouchEnd, { passive: false });
      
      return () => {
        scrollElement.removeEventListener('wheel', handleWheel);
        scrollElement.removeEventListener('touchstart', handleTouch.handleTouchStart);
        scrollElement.removeEventListener('touchmove', handleTouch.handleTouchMove);
        scrollElement.removeEventListener('touchend', handleTouch.handleTouchEnd);
      };
    }
  }, [currentWeek]);

  return (
    <Box sx={{ width: '100%', maxWidth: isMobile ? '100%' : 1200, mx: 'auto', px: isMobile ? 1 : 0 }}>
      {/* Header with navigation */}
      <Box sx={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', mb: 2 }}>
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
        ref={containerRef}
        sx={{
          height: isMobile ? '75vh' : '70vh',
          overflow: 'hidden',
          position: 'relative'
        }}
      >
        <Box
          sx={{
            display: 'flex',
            width: '300%',
            height: '100%',
            transform: `translateX(calc(-33.333% + ${translateX}px))`,
            transition: isAnimating ? 'transform 0.3s ease-out' : 'none',
            touchAction: 'pan-x'
          }}
        >
          {/* Previous Week */}
          <Box sx={{ width: '33.333%', display: 'flex', flexDirection: 'column', height: '100%' }}>
            <Box sx={{ display: 'flex', borderBottom: 1, borderColor: 'divider' }}>
              {weekdays.map((day, index) => (
                <Box
                  key={`prev-${day}`}
                  sx={{
                    flex: 1,
                    p: isMobile ? 1 : 2,
                    textAlign: 'center',
                    borderRight: index < 6 ? 1 : 0,
                    borderColor: 'divider',
                    minWidth: isMobile ? '14%' : 'auto'
                  }}
                >
                  <Typography variant={isMobile ? "body2" : "subtitle1"} fontWeight="bold">
                    {day}
                  </Typography>
                  <Typography variant={isMobile ? "body1" : "h6"} color="primary">
                    {formatDisplayDate(prevWeekDates[index])}
                  </Typography>
                </Box>
              ))}
            </Box>
            <Box sx={{ display: 'flex', flex: 1, overflow: 'hidden' }}>
              {prevWeekDates.map((date, index) => {
                const dateStr = formatDate(date);
                const dayEvents = events[dateStr] || [];
                return (
                  <Box
                    key={`prev-${dateStr}`}
                    sx={{
                      flex: 1,
                      p: isMobile ? 0.5 : 1,
                      borderRight: index < 6 ? 1 : 0,
                      borderColor: 'divider',
                      overflow: 'auto',
                      minWidth: isMobile ? '14%' : 'auto',
                      '&::-webkit-scrollbar': { display: 'none' },
                      msOverflowStyle: 'none',
                      scrollbarWidth: 'none'
                    }}
                  >
                    {dayEvents.map((event) => (
                      <Paper
                        key={event.id}
                        sx={{
                          p: isMobile ? 0.5 : 1,
                          mb: isMobile ? 0.5 : 1,
                          backgroundColor: 'primary.light',
                          color: 'primary.contrastText',
                          cursor: 'pointer',
                          transition: 'all 0.2s ease-in-out',
                          '&:hover': {
                            backgroundColor: 'primary.main',
                            transform: 'translateY(-2px)',
                            boxShadow: 4
                          }
                        }}
                      >
                        <Typography variant="caption" display="block">
                          {event.time}
                        </Typography>
                        <Typography variant={isMobile ? "caption" : "body2"} fontWeight="bold">
                          {event.title}
                        </Typography>
                        {event.description && !isMobile && (
                          <Typography variant="caption" sx={{ opacity: 0.8 }}>
                            {event.description}
                          </Typography>
                        )}
                      </Paper>
                    ))}
                  </Box>
                );
              })}
            </Box>
          </Box>

          {/* Current Week */}
          <Box ref={scrollRef} sx={{ width: '33.333%', display: 'flex', flexDirection: 'column', height: '100%' }}>
            <Box sx={{ display: 'flex', borderBottom: 1, borderColor: 'divider' }}>
              {weekdays.map((day, index) => (
                <Box
                  key={`current-${day}`}
                  sx={{
                    flex: 1,
                    p: isMobile ? 1 : 2,
                    textAlign: 'center',
                    borderRight: index < 6 ? 1 : 0,
                    borderColor: 'divider',
                    minWidth: isMobile ? '14%' : 'auto'
                  }}
                >
                  <Typography variant={isMobile ? "body2" : "subtitle1"} fontWeight="bold">
                    {day}
                  </Typography>
                  <Typography variant={isMobile ? "body1" : "h6"} color="primary">
                    {formatDisplayDate(weekDates[index])}
                  </Typography>
                </Box>
              ))}
            </Box>
            <Box sx={{ display: 'flex', flex: 1, overflow: 'hidden' }}>
              {weekDates.map((date, index) => {
                const dateStr = formatDate(date);
                const dayEvents = events[dateStr] || [];
                return (
                  <Box
                    key={`current-${dateStr}`}
                    sx={{
                      flex: 1,
                      p: isMobile ? 0.5 : 1,
                      borderRight: index < 6 ? 1 : 0,
                      borderColor: 'divider',
                      overflow: 'auto',
                      minWidth: isMobile ? '14%' : 'auto',
                      '&::-webkit-scrollbar': { display: 'none' },
                      msOverflowStyle: 'none',
                      scrollbarWidth: 'none'
                    }}
                  >
                    {dayEvents.map((event) => (
                      <Paper
                        key={event.id}
                        sx={{
                          p: isMobile ? 0.5 : 1,
                          mb: isMobile ? 0.5 : 1,
                          backgroundColor: 'primary.light',
                          color: 'primary.contrastText',
                          cursor: 'pointer',
                          transition: 'all 0.2s ease-in-out',
                          '&:hover': {
                            backgroundColor: 'primary.main',
                            transform: 'translateY(-2px)',
                            boxShadow: 4
                          }
                        }}
                      >
                        <Typography variant="caption" display="block">
                          {event.time}
                        </Typography>
                        <Typography variant={isMobile ? "caption" : "body2"} fontWeight="bold">
                          {event.title}
                        </Typography>
                        {event.description && !isMobile && (
                          <Typography variant="caption" sx={{ opacity: 0.8 }}>
                            {event.description}
                          </Typography>
                        )}
                      </Paper>
                    ))}
                  </Box>
                );
              })}
            </Box>
          </Box>

          {/* Next Week */}
          <Box sx={{ width: '33.333%', display: 'flex', flexDirection: 'column', height: '100%' }}>
            <Box sx={{ display: 'flex', borderBottom: 1, borderColor: 'divider' }}>
              {weekdays.map((day, index) => (
                <Box
                  key={`next-${day}`}
                  sx={{
                    flex: 1,
                    p: isMobile ? 1 : 2,
                    textAlign: 'center',
                    borderRight: index < 6 ? 1 : 0,
                    borderColor: 'divider',
                    minWidth: isMobile ? '14%' : 'auto'
                  }}
                >
                  <Typography variant={isMobile ? "body2" : "subtitle1"} fontWeight="bold">
                    {day}
                  </Typography>
                  <Typography variant={isMobile ? "body1" : "h6"} color="primary">
                    {formatDisplayDate(nextWeekDates[index])}
                  </Typography>
                </Box>
              ))}
            </Box>
            <Box sx={{ display: 'flex', flex: 1, overflow: 'hidden' }}>
              {nextWeekDates.map((date, index) => {
                const dateStr = formatDate(date);
                const dayEvents = events[dateStr] || [];
                return (
                  <Box
                    key={`next-${dateStr}`}
                    sx={{
                      flex: 1,
                      p: isMobile ? 0.5 : 1,
                      borderRight: index < 6 ? 1 : 0,
                      borderColor: 'divider',
                      overflow: 'auto',
                      minWidth: isMobile ? '14%' : 'auto',
                      '&::-webkit-scrollbar': { display: 'none' },
                      msOverflowStyle: 'none',
                      scrollbarWidth: 'none'
                    }}
                  >
                    {dayEvents.map((event) => (
                      <Paper
                        key={event.id}
                        sx={{
                          p: isMobile ? 0.5 : 1,
                          mb: isMobile ? 0.5 : 1,
                          backgroundColor: 'primary.light',
                          color: 'primary.contrastText',
                          cursor: 'pointer',
                          transition: 'all 0.2s ease-in-out',
                          '&:hover': {
                            backgroundColor: 'primary.main',
                            transform: 'translateY(-2px)',
                            boxShadow: 4
                          }
                        }}
                      >
                        <Typography variant="caption" display="block">
                          {event.time}
                        </Typography>
                        <Typography variant={isMobile ? "caption" : "body2"} fontWeight="bold">
                          {event.title}
                        </Typography>
                        {event.description && !isMobile && (
                          <Typography variant="caption" sx={{ opacity: 0.8 }}>
                            {event.description}
                          </Typography>
                        )}
                      </Paper>
                    ))}
                  </Box>
                );
              })}
            </Box>
          </Box>
        </Box>
      </Box>
    </Box>
  );
};

export default WeeklyCalendar;