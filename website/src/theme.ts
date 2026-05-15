import { createTheme, alpha } from '@mui/material/styles';

/* App-wide visual identity. A warm, heraldic "festival" dark theme:
   gold primary, crimson secondary, warm near-black surfaces, a display
   serif for page titles. Every page inherits this — the Classifica
   field reads its colours from the theme too, so it restyles in step. */

const DISPLAY = "'Cinzel', 'Times New Roman', Georgia, serif";
const SANS =
  '-apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Helvetica Neue", Arial, sans-serif';

const GOLD = '#e2ad45';
const CRIMSON = '#c9434b';
const BG = '#15120d';
const PAPER = '#1f1a12';

const theme = createTheme({
  palette: {
    mode: 'dark',
    primary: { main: GOLD, light: '#f1c870', dark: '#a97c1d', contrastText: '#1a1206' },
    secondary: { main: CRIMSON, light: '#dc6a70', dark: '#962f36', contrastText: '#fff' },
    background: { default: BG, paper: PAPER },
    text: {
      primary: '#f4ecdd',
      secondary: alpha('#f4ecdd', 0.62),
      disabled: alpha('#f4ecdd', 0.34),
    },
    divider: alpha('#f4ecdd', 0.13),
    success: { main: '#6fae5f' },
    warning: { main: '#e0a13a' },
    error: { main: '#d2595f' },
  },
  shape: { borderRadius: 12 },
  typography: {
    fontFamily: SANS,
    h1: { fontFamily: DISPLAY, fontWeight: 700 },
    h2: { fontFamily: DISPLAY, fontWeight: 700 },
    h3: { fontFamily: DISPLAY, fontWeight: 700 },
    h4: { fontFamily: DISPLAY, fontWeight: 600, letterSpacing: '.4px' },
    h5: { fontWeight: 700 },
    h6: { fontWeight: 700 },
    subtitle1: { fontWeight: 600 },
    button: { textTransform: 'none', fontWeight: 600 },
  },
  components: {
    MuiCssBaseline: {
      styleOverrides: {
        body: {
          backgroundColor: BG,
          // Subtle warm vignette so flat surfaces don't feel dead.
          backgroundImage: `radial-gradient(1200px 600px at 50% -10%, ${alpha(
            GOLD,
            0.06,
          )}, transparent 60%)`,
          backgroundAttachment: 'fixed',
        },
        '*::-webkit-scrollbar': { width: 10, height: 10 },
        '*::-webkit-scrollbar-thumb': {
          backgroundColor: alpha('#f4ecdd', 0.16),
          borderRadius: 8,
        },
        '*::-webkit-scrollbar-thumb:hover': { backgroundColor: alpha('#f4ecdd', 0.26) },
        '::selection': { backgroundColor: alpha(GOLD, 0.32) },
      },
    },
    // Kill MUI's dark elevation overlay — it greys/muddies every surface.
    MuiPaper: { styleOverrides: { root: { backgroundImage: 'none' } } },
    MuiCard: {
      defaultProps: { elevation: 0 },
      styleOverrides: {
        root: {
          border: `1px solid ${alpha('#f4ecdd', 0.1)}`,
          backgroundColor: PAPER,
          transition: 'border-color .2s ease, transform .2s ease, box-shadow .2s ease',
        },
      },
    },
    MuiButton: {
      defaultProps: { disableElevation: true },
      styleOverrides: { root: { borderRadius: 999 } },
    },
    MuiChip: { styleOverrides: { root: { fontWeight: 600 } } },
    MuiAppBar: {
      styleOverrides: {
        colorPrimary: {
          backgroundColor: PAPER,
          color: '#f4ecdd',
          backgroundImage: 'none',
          borderBottom: `1px solid ${alpha('#f4ecdd', 0.12)}`,
          boxShadow: 'none',
        },
      },
    },
    MuiDrawer: {
      styleOverrides: {
        paper: {
          backgroundColor: PAPER,
          borderRight: `1px solid ${alpha('#f4ecdd', 0.1)}`,
        },
      },
    },
    MuiListItemButton: {
      styleOverrides: {
        root: {
          margin: '2px 8px',
          borderRadius: 10,
          '&.Mui-selected': {
            backgroundColor: alpha(GOLD, 0.16),
            color: GOLD,
            '& .MuiListItemIcon-root': { color: GOLD },
            '&:hover': { backgroundColor: alpha(GOLD, 0.22) },
          },
        },
      },
    },
    MuiTableCell: {
      styleOverrides: {
        root: { borderColor: alpha('#f4ecdd', 0.08) },
        head: { fontWeight: 700, color: alpha('#f4ecdd', 0.7) },
      },
    },
  },
});

export default theme;
