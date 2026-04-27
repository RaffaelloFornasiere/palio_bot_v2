import React, { useEffect } from 'react';
import { Navigate, Outlet, useLocation } from 'react-router-dom';
import { Box, CircularProgress } from '@mui/material';
import { useAuthStore, isAuthenticated } from '../store/authStore';

const RequireAuth: React.FC = () => {
  const location = useLocation();
  const store = useAuthStore();
  const { initialized, init } = store;

  useEffect(() => {
    if (!initialized) init();
  }, [initialized, init]);

  if (!initialized) {
    return (
      <Box sx={{ minHeight: '100vh', display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
        <CircularProgress />
      </Box>
    );
  }

  if (!isAuthenticated(store)) {
    return <Navigate to="/edit/login" replace state={{ from: location }} />;
  }

  return <Outlet />;
};

export default RequireAuth;
