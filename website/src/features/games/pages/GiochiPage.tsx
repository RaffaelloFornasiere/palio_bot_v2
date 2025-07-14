import React from 'react';
import { Container, Typography, Box } from '@mui/material';

const GiochiPage: React.FC = () => {
  return (
    <Container maxWidth="lg">
      <Box sx={{ mt: 4, mb: 4 }}>
        <Typography variant="h4" component="h1" gutterBottom>
          Giochi
        </Typography>
        <Typography variant="body1">
          Questa è la pagina dei giochi.
        </Typography>
      </Box>
    </Container>
  );
};

export default GiochiPage;