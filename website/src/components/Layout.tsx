import React, { useState, useRef, useCallback } from 'react';
import { 
  Box, 
  Drawer, 
  List, 
  ListItem, 
  ListItemButton, 
  ListItemIcon, 
  ListItemText,
  Toolbar,
  Typography,
  Divider,
  IconButton,
  AppBar,
  useTheme,
  useMediaQuery
} from '@mui/material';
import { 
  Leaderboard as LeaderboardIcon,
  SportsEsports as GamesIcon,
  CalendarMonth as CalendarIcon,
  VideogameAsset as ArcadeIcon,
  FavoriteRounded as HeartIcon,
  Menu as MenuIcon
} from '@mui/icons-material';
import { Link as RouterLink, Outlet, useLocation, useNavigate } from 'react-router-dom';
import { useYear } from '../contexts/YearContext';
import BorgoPollPrompt from '../features/poll/BorgoPollPrompt';

const drawerWidth = 240;

// Hidden entrance to the edit section: tap the "Palio" title 7 times.
// Pure discoverability — real access control is Firebase auth on /edit.
const SECRET_TAP_COUNT = 7;
const SECRET_TAP_WINDOW_MS = 2000;

const Layout: React.FC = () => {
  const location = useLocation();
  const navigate = useNavigate();
  const { selectedYear } = useYear();
  const theme = useTheme();
  const isMobile = useMediaQuery(theme.breakpoints.down('md'));
  const [mobileOpen, setMobileOpen] = useState(false);

  const tapCountRef = useRef(0);
  const tapTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  const handleDrawerToggle = () => {
    setMobileOpen(!mobileOpen);
  };

  // Count taps on the title; reach SECRET_TAP_COUNT within the window to
  // reveal the edit section. The window resets the counter if taps stall.
  const handleSecretTap = useCallback(() => {
    if (tapTimerRef.current) {
      clearTimeout(tapTimerRef.current);
    }
    tapCountRef.current += 1;
    if (tapCountRef.current >= SECRET_TAP_COUNT) {
      tapCountRef.current = 0;
      navigate('/edit');
      return;
    }
    tapTimerRef.current = setTimeout(() => {
      tapCountRef.current = 0;
    }, SECRET_TAP_WINDOW_MS);
  }, [navigate]);

  // Create year-aware menu items
  const menuItems = [
    { text: 'Classifica', icon: <LeaderboardIcon />, path: selectedYear ? `/${selectedYear}/classifica` : '/classifica' },
    { text: 'Giochi', icon: <GamesIcon />, path: selectedYear ? `/${selectedYear}/giochi` : '/giochi' },
    { text: 'Calendario', icon: <CalendarIcon />, path: selectedYear ? `/${selectedYear}/calendario` : '/calendario' },
    { text: 'Mini-giochi', icon: <ArcadeIcon />, path: selectedYear ? `/${selectedYear}/gioco` : '/gioco' },
    // Poll is always live (current year) — deliberately not year-aware.
    { text: 'Borgo più amato', icon: <HeartIcon />, path: '/borgo-amato' },
  ];

  // Helper function to check if current path matches menu item
  const isItemSelected = (itemPath: string) => {
    const pathSegments = location.pathname.split('/').filter(Boolean);
    const itemSegments = itemPath.split('/').filter(Boolean);
    
    // If both have year prefix, compare the page part
    if (pathSegments.length >= 2 && itemSegments.length >= 2) {
      return pathSegments[1] === itemSegments[1];
    }
    
    // If neither has year prefix, compare directly
    if (pathSegments.length === 1 && itemSegments.length === 1) {
      return pathSegments[0] === itemSegments[0];
    }
    
    return false;
  };

  const brand = (
    <Box
      onClick={handleSecretTap}
      sx={{ userSelect: 'none', cursor: 'default', lineHeight: 1, minWidth: 0 }}
    >
      <Typography
        noWrap
        sx={{
          fontFamily: "'Cinzel', serif",
          fontWeight: 700,
          fontSize: '1.05rem',
          letterSpacing: '.5px',
          color: 'primary.main',
        }}
      >
        Palio dei Borghi
      </Typography>
      <Typography
        noWrap
        sx={{
          fontSize: '.66rem',
          letterSpacing: '.34em',
          textTransform: 'uppercase',
          color: 'text.secondary',
          mt: '2px',
        }}
      >
        Artegna
      </Typography>
    </Box>
  );

  const drawer = (
    <div>
      <Toolbar>{brand}</Toolbar>
      <Divider />
      <List>
        {menuItems.map((item) => (
          <ListItem key={item.text} disablePadding>
            <ListItemButton
              component={RouterLink}
              to={item.path}
              selected={isItemSelected(item.path)}
              onClick={isMobile ? handleDrawerToggle : undefined}
            >
              <ListItemIcon>
                {item.icon}
              </ListItemIcon>
              <ListItemText primary={item.text} />
            </ListItemButton>
          </ListItem>
        ))}
      </List>
    </div>
  );

  return (
    <Box sx={{ display: 'flex' }}>
      {isMobile && (
        <AppBar
          position="fixed"
          sx={{
            width: '100%',
            zIndex: theme.zIndex.drawer + 1,
          }}
        >
          <Toolbar>
            <IconButton
              color="inherit"
              aria-label="open drawer"
              edge="start"
              onClick={handleDrawerToggle}
              sx={{ mr: 2 }}
            >
              <MenuIcon />
            </IconButton>
            {brand}
          </Toolbar>
        </AppBar>
      )}
      
      <Box
        component="nav"
        sx={{ width: { md: drawerWidth }, flexShrink: { md: 0 } }}
      >
        {isMobile ? (
          <Drawer
            variant="temporary"
            open={mobileOpen}
            onClose={handleDrawerToggle}
            ModalProps={{
              keepMounted: true, // Better open performance on mobile.
            }}
            sx={{
              '& .MuiDrawer-paper': {
                boxSizing: 'border-box',
                width: drawerWidth,
              },
            }}
          >
            {drawer}
          </Drawer>
        ) : (
          <Drawer
            variant="permanent"
            sx={{
              '& .MuiDrawer-paper': {
                boxSizing: 'border-box',
                width: drawerWidth,
              },
            }}
            open
          >
            {drawer}
          </Drawer>
        )}
      </Box>
      
      <Box
        component="main"
        sx={{
          flexGrow: 1,
          width: { md: `calc(100% - ${drawerWidth}px)` },
          pt: isMobile ? 8 : 0, // Add top margin on mobile to account for AppBar
          height: isMobile ? 'calc(100vh - 64px)' : '100vh',
          overflow: 'auto',
        }}
      >
        <Outlet />
      </Box>

      {/* First-visit vote prompt (dismissable); silent if poll/backend off */}
      <BorgoPollPrompt />
    </Box>
  );
};

export default Layout;