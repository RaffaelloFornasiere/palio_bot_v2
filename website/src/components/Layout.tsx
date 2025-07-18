import React, { useState } from 'react';
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
  Menu as MenuIcon
} from '@mui/icons-material';
import { Link as RouterLink, Outlet, useLocation } from 'react-router-dom';
import { useYear } from '../contexts/YearContext';

const drawerWidth = 240;

const Layout: React.FC = () => {
  const location = useLocation();
  const { selectedYear } = useYear();
  const theme = useTheme();
  const isMobile = useMediaQuery(theme.breakpoints.down('md'));
  const [mobileOpen, setMobileOpen] = useState(false);

  const handleDrawerToggle = () => {
    setMobileOpen(!mobileOpen);
  };

  // Create year-aware menu items
  const menuItems = [
    { text: 'Classifica', icon: <LeaderboardIcon />, path: selectedYear ? `/${selectedYear}/classifica` : '/classifica' },
    { text: 'Giochi', icon: <GamesIcon />, path: selectedYear ? `/${selectedYear}/giochi` : '/giochi' },
    { text: 'Calendario', icon: <CalendarIcon />, path: selectedYear ? `/${selectedYear}/calendario` : '/calendario' },
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

  const drawer = (
    <div>
      <Toolbar>
        <Typography variant="h6" noWrap component="div">
          Palio
        </Typography>
      </Toolbar>
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
            <Typography variant="h6" noWrap component="div">
              Palio
            </Typography>
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
    </Box>
  );
};

export default Layout;