import React from 'react';
import { Container, Typography, Box } from '@mui/material';

const ClassificaPage: React.FC = () => {
  return (
    <Container maxWidth="lg">
      <Box sx={{ mt: 4, mb: 4 }}>
        <Typography variant="h4" component="h1" gutterBottom>
          Classifica
        </Typography>
        <Typography variant="body1">
          Questa è la pagina della classifica.
        </Typography>
      </Box>
    </Container>
  );
};

export default ClassificaPage;