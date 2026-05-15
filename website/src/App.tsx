import React from 'react';
import { BrowserRouter as Router, Routes, Route, Navigate, useParams } from 'react-router-dom';
import { ThemeProvider, createTheme, CssBaseline } from '@mui/material';
import { YearProvider } from './contexts/YearContext';
import Layout from './components/Layout';
import LeaderboardPage from './features/leaderboard/components/MascotRace';
import GamesPage from './features/games/pages/GiochiPage';
import GiocoDettagliPage from './features/games/pages/GiocoDettagliPage';
import CalendarPage from './features/calendar/pages/CalendarioPage';
import LoginPage from './features/editor/pages/LoginPage';
import EditorHomePage from './features/editor/pages/EditorHomePage';
import EditLeaderboardPage from './features/editor/pages/EditLeaderboardPage';
import LeaderboardOverviewView from './features/editor/pages/LeaderboardOverviewView';
import LeaderboardGameView from './features/editor/pages/LeaderboardGameView';
import EditGameStatusPage from './features/editor/pages/EditGameStatusPage';
import GameStatusListView from './features/editor/pages/GameStatusListView';
import GameStatusDetailView from './features/editor/pages/GameStatusDetailView';
import RequireAuth from './features/editor/components/RequireAuth';
import './App.css';

// Component to handle backward compatibility redirects
const BackwardCompatRedirect: React.FC<{ type: string }> = ({ type }) => {
  const { year } = useParams<{ year: string }>();
  return <Navigate to={`/${year}/${type}`} replace />;
};

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
        <YearProvider>
          <Routes>
            {/* Editor (authenticated, separate layout) */}
            <Route path="/edit/login" element={<LoginPage />} />
            <Route path="/edit" element={<RequireAuth />}>
              <Route index element={<EditorHomePage />} />
              <Route path="leaderboard" element={<EditLeaderboardPage />}>
                <Route index element={<LeaderboardOverviewView />} />
                <Route path=":gameId" element={<LeaderboardGameView />} />
              </Route>
              <Route path="games" element={<EditGameStatusPage />}>
                <Route index element={<GameStatusListView />} />
                <Route path=":gameId" element={<GameStatusDetailView />} />
              </Route>
            </Route>

            <Route path="/" element={<Layout />}>
              <Route index element={<Navigate to="/classifica" replace />} />
              
              {/* Current year routes */}
              <Route path="classifica" element={<LeaderboardPage />} />
              <Route path="giochi" element={<GamesPage />} />
              <Route path="giochi/:gameId" element={<GiocoDettagliPage />} />
              <Route path="calendario" element={<CalendarPage />} />
              
              {/* Year-first routes */}
              <Route path=":year">
                <Route index element={<Navigate to="classifica" replace />} />
                <Route path="classifica" element={<LeaderboardPage />} />
                <Route path="giochi" element={<GamesPage />} />
                <Route path="giochi/:gameId" element={<GiocoDettagliPage />} />
                <Route path="calendario" element={<CalendarPage />} />
              </Route>
              
              {/* Backward compatibility redirects */}
              <Route path="classifica/:year" element={<BackwardCompatRedirect type="classifica" />} />
              <Route path="giochi/:year/overview" element={<BackwardCompatRedirect type="giochi" />} />
              <Route path="calendario/:year" element={<BackwardCompatRedirect type="calendario" />} />
            </Route>
          </Routes>
        </YearProvider>
      </Router>
    </ThemeProvider>
  );
}

export default App;
