import React from 'react';
import { Box, BoxProps } from '@mui/material';
import { keyframes } from '@mui/system';

interface AnimatedBoxProps extends BoxProps {
  animationKey: string | number;
  direction?: 'left' | 'right';
  duration?: number;
}

const slideInFromLeft = keyframes`
  from {
    transform: translateX(-100%);
    opacity: 0;
  }
  to {
    transform: translateX(0);
    opacity: 1;
  }
`;

const slideInFromRight = keyframes`
  from {
    transform: translateX(100%);
    opacity: 0;
  }
  to {
    transform: translateX(0);
    opacity: 1;
  }
`;

const AnimatedBox: React.FC<AnimatedBoxProps> = ({ 
  animationKey, 
  direction = 'left', 
  duration = 0.3,
  children, 
  sx,
  ...props 
}) => {
  const animation = direction === 'left' ? slideInFromLeft : slideInFromRight;
  
  return (
    <Box
      key={animationKey}
      sx={{
        animation: `${animation} ${duration}s ease-out`,
        ...sx
      }}
      {...props}
    >
      {children}
    </Box>
  );
};

export default AnimatedBox;