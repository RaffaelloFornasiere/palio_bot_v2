import React from 'react';
import { BrowserRouter as Router, Routes, Route, Navigate } from 'react-router-dom';
import { ThemeProvider, createTheme, CssBaseline } from '@mui/material';
import Layout from './components/Layout';
import LeaderboardPage from './features/leaderboard/pages/ClassificaPage';
import GamesPage from './features/games/pages/GiochiPage';
import GiocoDettagliPage from './features/games/pages/GiocoDettagliPage';
import CalendarPage from './features/calendar/pages/CalendarioPage';
import './App.css';

const theme = createTheme({
  palette: {
    mode: 'dark',
  },
});

function App() {
  return (
    <ThemeProvider theme={theme}>
      <CssBaseline />
      <Router>
        <Routes>
          <Route path="/" element={<Layout />}>
            <Route index element={<Navigate to="/classifica" replace />} />
            <Route path="classifica" element={<LeaderboardPage />} />
            <Route path="giochi" element={<GamesPage />} />
            <Route path="giochi/:gameId" element={<GiocoDettagliPage />} />
            <Route path="calendario" element={<CalendarPage />} />
          </Route>
        </Routes>
      </Router>
    </ThemeProvider>
  );
}

export default App;
