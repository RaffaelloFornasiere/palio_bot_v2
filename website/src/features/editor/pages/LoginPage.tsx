import React, { useEffect } from 'react';
import { useNavigate, useLocation } from 'react-router-dom';
import {
  Box, Paper, Button, Typography, Alert, CircularProgress,
} from '@mui/material';
import GoogleIcon from '@mui/icons-material/Google';
import LockIcon from '@mui/icons-material/Lock';
import { useAuthStore, isAuthenticated } from '../store/authStore';

const LoginPage: React.FC = () => {
  const navigate = useNavigate();
  const location = useLocation();
  const store = useAuthStore();
  const { signIn, loading, error, initialized, authRequired, firebaseConfigured, init } = store;
  const authed = isAuthenticated(store);

  useEffect(() => {
    if (!initialized) init();
  }, [initialized, init]);

  useEffect(() => {
    if (authed) {
      const from = (location.state as any)?.from?.pathname || '/edit';
      navigate(from, { replace: true });
    }
  }, [authed, navigate, location.state]);

  if (!initialized) {
    return (
      <Box sx={{ minHeight: '100vh', display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
        <CircularProgress />
      </Box>
    );
  }

  return (
    <Box
      sx={{
        minHeight: '100vh',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        p: 2,
        bgcolor: 'background.default',
      }}
    >
      <Paper elevation={3} sx={{ p: 4, width: '100%', maxWidth: 400 }}>
        <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, mb: 3 }}>
          <LockIcon color="primary" />
          <Typography variant="h5">Editor</Typography>
        </Box>
        <Typography variant="body2" color="text.secondary" sx={{ mb: 3 }}>
          Area riservata. Accedi con Google.
        </Typography>

        {authRequired === false && (
          <Alert severity="info" sx={{ mb: 2 }}>
            Modalità sviluppo: autenticazione disabilitata.
            <Button onClick={() => navigate('/edit', { replace: true })} sx={{ mt: 1 }} size="small">
              Continua
            </Button>
          </Alert>
        )}

        {authRequired && !firebaseConfigured && (
          <Alert severity="error" sx={{ mb: 2 }}>
            Firebase non configurato sul server. Contatta l'amministratore.
          </Alert>
        )}

        {error && <Alert severity="error" sx={{ mb: 2 }}>{error}</Alert>}

        {firebaseConfigured && (
          <Button
            variant="contained"
            fullWidth
            size="large"
            startIcon={loading ? <CircularProgress size={20} color="inherit" /> : <GoogleIcon />}
            onClick={signIn}
            disabled={loading}
          >
            Accedi con Google
          </Button>
        )}
      </Paper>
    </Box>
  );
};

export default LoginPage;
