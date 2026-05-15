import React from 'react';
import {Link as RouterLink} from 'react-router-dom';
import {Container, Typography, Box, Card, CardActionArea, CardContent} from '@mui/material';

const GAMES = [
   {
      to: 'bros',
      emoji: '🍄',
      title: 'Super Borgo Bros',
      desc: 'Platformer alla Super Mario: corri, salta sui Goomba, prendi i funghi e raggiungi la bandiera.',
   },
   {
      to: 'dino',
      emoji: '🦖',
      title: 'Borgo Dino',
      desc: 'Endless runner alla Chrome Dino: salta i cactus, schiva i pterodattili, batti il record.',
   },
];

const MiniGamesPage: React.FC = () => (
   <Container maxWidth="lg">
      <Box sx={{mt: 4, mb: 4}}>
         <Box sx={{mb: 3}}>
            <Typography variant="h4" component="h1">
               Mini-giochi
            </Typography>
         </Box>

         <Box
            sx={{
               display: 'grid',
               gap: 2,
               gridTemplateColumns: {xs: '1fr', sm: '1fr 1fr'},
            }}
         >
            {GAMES.map((g) => (
               <Card key={g.to}>
                  <CardActionArea component={RouterLink} to={g.to} sx={{height: '100%'}}>
                     <CardContent>
                        <Typography variant="h2" sx={{lineHeight: 1, mb: 1}}>
                           {g.emoji}
                        </Typography>
                        <Typography variant="h6" gutterBottom>
                           {g.title}
                        </Typography>
                        <Typography variant="body2" color="text.secondary">
                           {g.desc}
                        </Typography>
                     </CardContent>
                  </CardActionArea>
               </Card>
            ))}
         </Box>
      </Box>
   </Container>
);

export default MiniGamesPage;
