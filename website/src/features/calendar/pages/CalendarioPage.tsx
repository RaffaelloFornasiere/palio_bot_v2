import React, { useState, useEffect } from 'react';
import { Typography, Box } from '@mui/material';
import FestivalCalendar, { CalEvent } from '../components/FestivalCalendar';
import { getPalioDataForYear } from '../../../utils/yearApi';
import { useYear } from '../../../contexts/YearContext';
import YearSelector from '../../../components/YearSelector';

const ymd = (d: Date) => {
  const y = d.getFullYear();
  const m = String(d.getMonth() + 1).padStart(2, '0');
  const day = String(d.getDate()).padStart(2, '0');
  return `${y}-${m}-${day}`;
};

const CalendarioPage: React.FC = () => {
  const [events, setEvents] = useState<{ [date: string]: CalEvent[] }>({});
  const { selectedYear } = useYear();

  useEffect(() => {
    getPalioDataForYear(selectedYear)
      .then(response => {
        if (response.error) {
          throw new Error('Failed to fetch palio data');
        }
        const data = response.data!;
        const byDay: { [date: string]: CalEvent[] } = {};

        const push = (
          id: string,
          title: string,
          subtitle: string | undefined,
          start: Date,
          end: Date,
        ) => {
          const key = ymd(start);
          (byDay[key] ??= []).push({ id, title, subtitle, start, end });
        };

        data.games.forEach(game => {
          game.dates.forEach((gd, i) => {
            push(
              `${game.id}-${i}`,
              game.name,
              game.dates.length > 1 ? gd.subtitle || undefined : undefined,
              new Date(gd.start_datetime),
              new Date(gd.end_datetime),
            );
          });
        });

        data.non_game_events.forEach(event => {
          event.dates.forEach((ed, i) => {
            push(
              `${event.name}-${i}`,
              event.name,
              event.dates.length > 1 ? ed.subtitle || undefined : undefined,
              new Date(ed.start_datetime),
              new Date(ed.end_datetime),
            );
          });
        });

        setEvents(byDay);
      })
      .catch(error => {
        console.error('Error loading calendar data:', error);
      });
  }, [selectedYear]);

  return (
    <Box sx={{ height: '100%', display: 'flex', flexDirection: 'column' }}>
      <Box sx={{ p: 2, display: 'flex', justifyContent: 'space-between', alignItems: 'center', flexShrink: 0 }}>
        <Typography variant="h4" component="h1">
          Calendario Eventi
        </Typography>
        <YearSelector />
      </Box>
      <FestivalCalendar events={events} />
    </Box>
  );
};

export default CalendarioPage;
