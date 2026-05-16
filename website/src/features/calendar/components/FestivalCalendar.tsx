import React, { useEffect, useMemo, useRef, useState } from 'react';
import { Box, Typography, Paper, Chip } from '@mui/material';
import { useSearchParams } from 'react-router-dom';

export interface CalEvent {
  id: string;
  title: string;
  subtitle?: string;
  start: Date;
  end: Date;
}

interface Props {
  events: { [date: string]: CalEvent[] };
}

const ymd = (d: Date) => {
  const y = d.getFullYear();
  const m = String(d.getMonth() + 1).padStart(2, '0');
  const day = String(d.getDate()).padStart(2, '0');
  return `${y}-${m}-${day}`;
};

const hhmm = (d: Date) =>
  d.toLocaleTimeString('it-IT', { hour: '2-digit', minute: '2-digit', hour12: false });

const parseDay = (s: string) => {
  const [y, m, d] = s.split('-').map(Number);
  return new Date(y, m - 1, d);
};

const NowDivider: React.FC<{ time: string }> = ({ time }) => (
  <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, my: 1 }}>
    <Box sx={{ width: 48, flex: 'none' }} />
    <Box sx={{ flex: 1, borderTop: '2px dashed', borderColor: 'secondary.main', opacity: 0.6 }} />
    <Chip size="small" color="secondary" label={`ORA ${time}`} sx={{ flex: 'none', fontWeight: 700 }} />
    <Box sx={{ flex: 1, borderTop: '2px dashed', borderColor: 'secondary.main', opacity: 0.6 }} />
  </Box>
);

/* Festival-centric calendar: a horizontal strip of the Palio days (the
   window is derived from the data itself, not hardcoded — so a variable
   opening Friday or a 31 July start just works) plus an hour-railed
   agenda for the selected day, with an "ORA" line and an Adesso/Prossimo
   banner while you're actually at the Palio. Selected day lives in the
   URL (?d=YYYY-MM-DD) so a day's programme is shareable. */
const FestivalCalendar: React.FC<Props> = ({ events }) => {
  const [params, setParams] = useSearchParams();
  const [now, setNow] = useState(() => new Date());

  // Keep "now" fresh so the ADESSO banner and ORA line stay live.
  useEffect(() => {
    const t = setInterval(() => setNow(new Date()), 60_000);
    return () => clearInterval(t);
  }, []);

  const festivalDays = useMemo(
    () => Object.keys(events).filter((k) => events[k]?.length).sort(),
    [events],
  );

  const todayStr = ymd(now);
  const requested = params.get('d');
  const selectedDay =
    requested && festivalDays.includes(requested)
      ? requested
      : festivalDays.includes(todayStr)
        ? todayStr
        : (festivalDays[0] ?? null);

  const selectDay = (d: string) => {
    const next = new URLSearchParams(params);
    next.set('d', d);
    setParams(next, { replace: true });
  };

  // Keep the active chip scrolled into view when the day changes.
  const stripRef = useRef<HTMLDivElement>(null);
  useEffect(() => {
    const el = stripRef.current?.querySelector<HTMLElement>('[data-selected="true"]');
    el?.scrollIntoView({ inline: 'center', block: 'nearest', behavior: 'smooth' });
  }, [selectedDay]);

  if (festivalDays.length === 0) {
    return (
      <Typography variant="body2" color="text.secondary" sx={{ textAlign: 'center', mt: 6 }}>
        Nessun evento in programma per quest'anno.
      </Typography>
    );
  }

  const dayEvents = (selectedDay ? (events[selectedDay] ?? []) : [])
    .slice()
    .sort((a, b) => a.start.getTime() - b.start.getTime());

  const isToday = selectedDay === todayStr;
  const ongoing = isToday ? dayEvents.find((e) => e.start <= now && now < e.end) : undefined;
  const upcoming = isToday ? dayEvents.find((e) => e.start > now) : undefined;
  const nowIndex = isToday ? dayEvents.filter((e) => e.start <= now).length : -1;
  const dayOver =
    isToday && dayEvents.length > 0 && now > dayEvents[dayEvents.length - 1].end;

  return (
    <Box sx={{ display: 'flex', flexDirection: 'column', minHeight: 0, flex: 1 }}>
      {/* Palio day strip */}
      <Box
        ref={stripRef}
        sx={{
          display: 'flex',
          gap: 1,
          px: 2,
          pb: 1.5,
          overflowX: 'auto',
          flexShrink: 0,
          scrollSnapType: 'x proximity',
          '&::-webkit-scrollbar': { display: 'none' },
          scrollbarWidth: 'none',
        }}
      >
        {festivalDays.map((d, i) => {
          const date = parseDay(d);
          const sel = d === selectedDay;
          const isTd = d === todayStr;
          const opening = i === 0;
          return (
            <Box
              key={d}
              data-selected={sel}
              onClick={() => selectDay(d)}
              role="button"
              aria-pressed={sel}
              sx={{
                scrollSnapAlign: 'center',
                flex: 'none',
                minWidth: 64,
                px: 1.5,
                py: 1,
                borderRadius: 2,
                textAlign: 'center',
                cursor: 'pointer',
                position: 'relative',
                border: '1px solid',
                borderColor: sel ? 'primary.main' : 'divider',
                bgcolor: sel ? 'primary.main' : 'background.paper',
                color: sel ? 'primary.contrastText' : 'text.primary',
                transition: 'all .15s ease',
              }}
            >
              <Typography
                variant="caption"
                sx={{ textTransform: 'capitalize', display: 'block', lineHeight: 1.15 }}
              >
                {date.toLocaleDateString('it-IT', { weekday: 'short' })}
              </Typography>
              <Typography variant="h6" sx={{ lineHeight: 1.15 }}>
                {date.getDate()}
              </Typography>
              <Typography
                variant="caption"
                sx={{ display: 'block', lineHeight: 1.15, opacity: 0.8 }}
              >
                {date.toLocaleDateString('it-IT', { month: 'short' })}
              </Typography>
              {isTd && (
                <Box
                  sx={{
                    fontSize: 9,
                    fontWeight: 700,
                    mt: 0.25,
                    letterSpacing: '.06em',
                    color: sel ? 'primary.contrastText' : 'secondary.main',
                  }}
                >
                  OGGI
                </Box>
              )}
              {opening && !isTd && (
                <Box
                  component="span"
                  title="Apertura del Palio"
                  sx={{ position: 'absolute', top: 2, right: 5, fontSize: 11 }}
                >
                  🚩
                </Box>
              )}
            </Box>
          );
        })}
      </Box>

      {/* Adesso / Prossimo — only while you're at the Palio */}
      {(ongoing || upcoming) && (
        <Box sx={{ px: 2, pb: 1, flexShrink: 0 }}>
          <Paper
            variant="outlined"
            sx={{
              p: 1.5,
              borderColor: 'secondary.main',
              display: 'flex',
              flexDirection: 'column',
              gap: 0.75,
            }}
          >
            {ongoing && (
              <Box sx={{ display: 'flex', alignItems: 'baseline', gap: 1 }}>
                <Chip size="small" color="secondary" label="ADESSO" sx={{ fontWeight: 700 }} />
                <Typography variant="body2" fontWeight={700} noWrap sx={{ minWidth: 0 }}>
                  {ongoing.title}
                </Typography>
                <Typography variant="caption" color="text.secondary" sx={{ ml: 'auto', flex: 'none' }}>
                  fino alle {hhmm(ongoing.end)}
                </Typography>
              </Box>
            )}
            {upcoming && (
              <Box sx={{ display: 'flex', alignItems: 'baseline', gap: 1 }}>
                <Chip size="small" variant="outlined" label="POI" />
                <Typography variant="body2" noWrap sx={{ minWidth: 0 }}>
                  {upcoming.title}
                </Typography>
                <Typography variant="caption" color="text.secondary" sx={{ ml: 'auto', flex: 'none' }}>
                  alle {hhmm(upcoming.start)}
                </Typography>
              </Box>
            )}
          </Paper>
        </Box>
      )}

      {/* Selected day header */}
      {selectedDay && (
        <Typography
          variant="h6"
          sx={{
            px: 2,
            pb: 1,
            color: 'primary.main',
            textTransform: 'capitalize',
            flexShrink: 0,
          }}
        >
          {parseDay(selectedDay).toLocaleDateString('it-IT', {
            weekday: 'long',
            day: 'numeric',
            month: 'long',
          })}
        </Typography>
      )}

      {/* Hour-railed agenda */}
      <Box
        sx={{
          flex: 1,
          overflowY: 'auto',
          px: 2,
          pb: 3,
          '&::-webkit-scrollbar': { display: 'none' },
          scrollbarWidth: 'none',
        }}
      >
        {dayEvents.length === 0 ? (
          <Typography variant="body2" color="text.secondary" sx={{ textAlign: 'center', mt: 4 }}>
            Nessun evento in questo giorno.
          </Typography>
        ) : (
          <Box>
            {dayEvents.map((e, i) => {
              const past = isToday && now >= e.end;
              const live = ongoing?.id === e.id;
              return (
                <React.Fragment key={e.id}>
                  {isToday && i === nowIndex && !dayOver && <NowDivider time={hhmm(now)} />}
                  <Box sx={{ display: 'flex', gap: 1.5, opacity: past ? 0.5 : 1 }}>
                    <Box sx={{ width: 48, flexShrink: 0, textAlign: 'right', pt: 0.25 }}>
                      <Typography
                        variant="caption"
                        fontWeight={700}
                        sx={{ fontVariantNumeric: 'tabular-nums' }}
                      >
                        {hhmm(e.start)}
                      </Typography>
                    </Box>
                    <Box
                      sx={{
                        position: 'relative',
                        pl: 2,
                        pb: 1.5,
                        flex: 1,
                        minWidth: 0,
                        borderLeft: '2px solid',
                        borderColor: live ? 'secondary.main' : 'divider',
                      }}
                    >
                      <Box
                        sx={{
                          position: 'absolute',
                          left: -5,
                          top: 7,
                          width: 8,
                          height: 8,
                          borderRadius: '50%',
                          bgcolor: live ? 'secondary.main' : 'primary.main',
                        }}
                      />
                      <Paper sx={{ p: 1.25, bgcolor: 'primary.light', color: 'primary.contrastText' }}>
                        <Typography variant="body1" fontWeight={700}>
                          {e.title}
                        </Typography>
                        {e.subtitle && (
                          <Typography variant="body2" sx={{ fontStyle: 'italic', opacity: 0.9 }}>
                            {e.subtitle}
                          </Typography>
                        )}
                        <Typography variant="caption" sx={{ opacity: 0.85 }}>
                          {hhmm(e.start)} – {hhmm(e.end)}
                        </Typography>
                      </Paper>
                    </Box>
                  </Box>
                  {isToday && dayOver && i === dayEvents.length - 1 && (
                    <Typography
                      variant="caption"
                      color="text.secondary"
                      sx={{ display: 'block', textAlign: 'center', mt: 1 }}
                    >
                      Programma di oggi concluso.
                    </Typography>
                  )}
                </React.Fragment>
              );
            })}
          </Box>
        )}
      </Box>
    </Box>
  );
};

export default FestivalCalendar;
