import React from 'react';
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
  Divider
} from '@mui/material';
import { 
  Leaderboard as LeaderboardIcon,
  SportsEsports as GamesIcon,
  CalendarMonth as CalendarIcon
} from '@mui/icons-material';
import { Link as RouterLink, Outlet, useLocation } from 'react-router-dom';

const drawerWidth = 240;

const Layout: React.FC = () => {
  const location = useLocation();

  const menuItems = [
    { text: 'Classifica', icon: <LeaderboardIcon />, path: '/classifica' },
    { text: 'Giochi', icon: <GamesIcon />, path: '/giochi' },
    { text: 'Calendario', icon: <CalendarIcon />, path: '/calendario' },
  ];

  return (
    <Box sx={{ display: 'flex' }}>
      <Drawer
        sx={{
          width: drawerWidth,
          flexShrink: 0,
          '& .MuiDrawer-paper': {
            width: drawerWidth,
            boxSizing: 'border-box',
          },
        }}
        variant="permanent"
        anchor="left"
      >
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
                selected={location.pathname === item.path}
              >
                <ListItemIcon>
                  {item.icon}
                </ListItemIcon>
                <ListItemText primary={item.text} />
              </ListItemButton>
            </ListItem>
          ))}
        </List>
      </Drawer>
      <Box
        component="main"
        sx={{ flexGrow: 1, bgcolor: 'background.default', p: 3 }}
      >
        <Outlet />
      </Box>
    </Box>
  );
};

export default Layout;