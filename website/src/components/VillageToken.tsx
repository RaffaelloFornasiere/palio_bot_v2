import React from 'react';
import { Box } from '@mui/material';
import { MASCOTS, FALLBACK_EMOJI } from '../utils/villages';
import { curatedVillageColor, getContrastTextColor } from '../utils/colorUtils';

/* The mascot disc from the leaderboard race, reusable in static contexts.
   Same curated colour + contrast ring so it never vanishes on dark. */

interface Props {
  village: string;
  rawColor?: string;
  size?: number;
}

const VillageToken: React.FC<Props> = ({ village, rawColor, size = 28 }) => {
  const color = curatedVillageColor(rawColor || '#888888');
  return (
    <Box
      component="span"
      sx={{
        width: size,
        height: size,
        borderRadius: '50%',
        flexShrink: 0,
        display: 'inline-grid',
        placeItems: 'center',
        fontSize: size * 0.56,
        lineHeight: 1,
        background: color,
        color: getContrastTextColor(color),
        boxShadow:
          '0 0 0 1.5px rgba(255,255,255,.5), 0 2px 6px rgba(0,0,0,.45), 0 0 0 2px rgba(255,255,255,.22) inset',
      }}
    >
      {MASCOTS[village] || FALLBACK_EMOJI}
    </Box>
  );
};

export default VillageToken;
