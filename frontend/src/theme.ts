import { createTheme, ThemeOptions } from '@mui/material/styles';

// Define color palette for Aegis
const palette = {
  primary: {
    main: '#1976d2',
    light: '#42a5f5',
    dark: '#1565c0',
    contrastText: '#ffffff',
  },
  secondary: {
    main: '#dc004e',
    light: '#e33371',
    dark: '#9a0036',
    contrastText: '#ffffff',
  },
  error: {
    main: '#f44336',
    light: '#e57373',
    dark: '#d32f2f',
  },
  warning: {
    main: '#ff9800',
    light: '#ffb74d',
    dark: '#f57c00',
  },
  info: {
    main: '#2196f3',
    light: '#64b5f6',
    dark: '#1976d2',
  },
  success: {
    main: '#4caf50',
    light: '#81c784',
    dark: '#388e3c',
  },
  background: {
    default: '#f5f5f5',
    paper: '#ffffff',
  },
  severity: {
    P0: '#d32f2f',
    P1: '#f57c00',
    P2: '#fbc02d',
    P3: '#689f38',
    P4: '#1976d2',
  },
  status: {
    OPEN: '#f44336',
    ACKNOWLEDGED: '#ff9800',
    MITIGATING: '#2196f3',
    RESOLVED: '#4caf50',
    CLOSED: '#9e9e9e',
  },
};

const themeOptions: ThemeOptions = {
  palette: {
    mode: 'light',
    ...palette,
  },
  typography: {
    fontFamily: [
      '-apple-system',
      'BlinkMacSystemFont',
      '"Segoe UI"',
      'Roboto',
      '"Helvetica Neue"',
      'Arial',
      'sans-serif',
    ].join(','),
    h1: {
      fontSize: '2.5rem',
      fontWeight: 600,
    },
    h2: {
      fontSize: '2rem',
      fontWeight: 600,
    },
    h3: {
      fontSize: '1.75rem',
      fontWeight: 600,
    },
    h4: {
      fontSize: '1.5rem',
      fontWeight: 600,
    },
    h5: {
      fontSize: '1.25rem',
      fontWeight: 600,
    },
    h6: {
      fontSize: '1rem',
      fontWeight: 600,
    },
  },
  shape: {
    borderRadius: 8,
  },
  components: {
    MuiButton: {
      styleOverrides: {
        root: {
          textTransform: 'none',
          fontWeight: 500,
        },
      },
    },
    MuiCard: {
      styleOverrides: {
        root: {
          boxShadow: '0 2px 4px rgba(0,0,0,0.1)',
          '&:hover': {
            boxShadow: '0 4px 8px rgba(0,0,0,0.15)',
          },
        },
      },
    },
    MuiChip: {
      styleOverrides: {
        root: {
          fontWeight: 500,
        },
      },
    },
    MuiPaper: {
      styleOverrides: {
        elevation1: {
          boxShadow: '0 2px 4px rgba(0,0,0,0.1)',
        },
      },
    },
    MuiTableCell: {
      styleOverrides: {
        head: {
          fontWeight: 600,
          backgroundColor: '#fafafa',
        },
      },
    },
  },
};

// Create theme with custom palette
export const theme = createTheme(themeOptions);

// Export severity colors for use in components
export const severityColors = {
  P0: palette.severity.P0,
  P1: palette.severity.P1,
  P2: palette.severity.P2,
  P3: palette.severity.P3,
  P4: palette.severity.P4,
};

// Export status colors for use in components
export const statusColors = {
  OPEN: palette.status.OPEN,
  ACKNOWLEDGED: palette.status.ACKNOWLEDGED,
  MITIGATING: palette.status.MITIGATING,
  RESOLVED: palette.status.RESOLVED,
  CLOSED: palette.status.CLOSED,
};