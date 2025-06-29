import React from 'react';
import { Routes, Route, Navigate } from 'react-router-dom';
import { Box } from '@mui/material';

// Layout components
import Layout from './components/Layout';
import PrivateRoute from './components/PrivateRoute';

// Page components
import Dashboard from './pages/Dashboard';
import IncidentList from './pages/IncidentList';
import IncidentDetail from './pages/IncidentDetail';
import CreateIncident from './pages/CreateIncident';
import Reports from './pages/Reports';
import Settings from './pages/Settings';
import NotFound from './pages/NotFound';

// Hooks
import { useRealTimeUpdates } from './hooks/useRealTimeUpdates';
import { useNotifications } from './hooks/useNotifications';

const App: React.FC = () => {
  // Initialize real-time updates
  useRealTimeUpdates();
  
  // Initialize notification system
  useNotifications();

  return (
    <Box sx={{ display: 'flex' }}>
      <Routes>
        <Route path="/" element={<Layout />}>
          <Route index element={<Navigate to="/dashboard" replace />} />
          <Route
            path="dashboard"
            element={
              <PrivateRoute>
                <Dashboard />
              </PrivateRoute>
            }
          />
          <Route
            path="incidents"
            element={
              <PrivateRoute>
                <IncidentList />
              </PrivateRoute>
            }
          />
          <Route
            path="incidents/new"
            element={
              <PrivateRoute>
                <CreateIncident />
              </PrivateRoute>
            }
          />
          <Route
            path="incidents/:incidentId"
            element={
              <PrivateRoute>
                <IncidentDetail />
              </PrivateRoute>
            }
          />
          <Route
            path="reports"
            element={
              <PrivateRoute>
                <Reports />
              </PrivateRoute>
            }
          />
          <Route
            path="settings"
            element={
              <PrivateRoute>
                <Settings />
              </PrivateRoute>
            }
          />
          <Route path="*" element={<NotFound />} />
        </Route>
      </Routes>
    </Box>
  );
};

export default App;