import React from 'react';
import { Box, Typography } from '@mui/material';
import { alpha } from '@mui/material/styles';
import VillageToken from '../../components/VillageToken';
import { curatedVillageColor } from '../../utils/colorUtils';
import type { PollStats } from '../../utils/pollApi';

/* Ranked bar list shared by the vote dialog (after voting) and the
   stats page. Always shows every borgo, zero-count included, sorted by
   all-time votes desc. */

interface Props {
  stats: PollStats;
  villages: string[];
  colors: Record<string, string>;
  compact?: boolean;
}

const PollResults: React.FC<Props> = ({ stats, villages, colors, compact }) => {
  const counts = stats.total_counts || {};
  const ranked = [...villages].sort(
    (a, b) => (counts[b] || 0) - (counts[a] || 0) || a.localeCompare(b),
  );
  const max = Math.max(1, ...ranked.map((v) => counts[v] || 0));

  return (
    <Box sx={{ display: 'flex', flexDirection: 'column', gap: compact ? 1 : 1.5 }}>
      {ranked.map((v) => {
        const n = counts[v] || 0;
        const accent = curatedVillageColor(colors[v] || '#888888');
        const pct = stats.total_votes ? Math.round((n / stats.total_votes) * 100) : 0;
        return (
          <Box key={v} sx={{ display: 'flex', alignItems: 'center', gap: 1.25 }}>
            <VillageToken village={v} rawColor={colors[v]} size={compact ? 26 : 32} />
            <Box sx={{ flex: 1, minWidth: 0 }}>
              <Box
                sx={{
                  display: 'flex',
                  justifyContent: 'space-between',
                  alignItems: 'baseline',
                  gap: 1,
                  mb: 0.25,
                }}
              >
                <Typography variant="body2" fontWeight={700} noWrap>
                  {v}
                </Typography>
                <Typography variant="caption" color="text.secondary" sx={{ flexShrink: 0 }}>
                  {n} {n === 1 ? 'voto' : 'voti'} · {pct}%
                </Typography>
              </Box>
              <Box
                sx={{
                  height: compact ? 6 : 8,
                  borderRadius: 999,
                  bgcolor: alpha('#f4ecdd', 0.08),
                  overflow: 'hidden',
                }}
              >
                <Box
                  sx={{
                    width: `${Math.round(((n || 0) / max) * 100)}%`,
                    height: '100%',
                    borderRadius: 999,
                    bgcolor: accent,
                    transition: 'width .5s ease',
                  }}
                />
              </Box>
            </Box>
          </Box>
        );
      })}
      <Typography variant="caption" color="text.secondary" sx={{ mt: 0.5 }}>
        {stats.total_votes} {stats.total_votes === 1 ? 'voto totale' : 'voti totali'}
        {stats.today_votes ? ` · ${stats.today_votes} oggi` : ''}
      </Typography>
    </Box>
  );
};

export default PollResults;
