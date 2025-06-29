import React from 'react';
import {
  Grid,
  Paper,
  Typography,
  Box,
  Card,
  CardContent,
  IconButton,
  Skeleton,
} from '@mui/material';
import {
  TrendingUp,
  TrendingDown,
  Warning,
  CheckCircle,
  Schedule,
  BugReport,
  Refresh,
} from '@mui/icons-material';
import { useQuery } from 'react-query';

// Components
import IncidentStatusChart from '@/components/Charts/IncidentStatusChart';
import SeverityDistributionChart from '@/components/Charts/SeverityDistributionChart';
import RecentIncidents from '@/components/Dashboard/RecentIncidents';
import ActiveIncidentsBanner from '@/components/Dashboard/ActiveIncidentsBanner';
import MetricCard from '@/components/Dashboard/MetricCard';
import IncidentTimeline from '@/components/Dashboard/IncidentTimeline';

// Services
import { dashboardService } from '@/services/dashboardService';

// Types
import { DashboardMetrics } from '@/types';

const Dashboard: React.FC = () => {
  const {
    data: metrics,
    isLoading,
    error,
    refetch,
  } = useQuery<DashboardMetrics>(
    'dashboardMetrics',
    dashboardService.getMetrics,
    {
      refetchInterval: 30000, // Refresh every 30 seconds
    }
  );

  const handleRefresh = () => {
    refetch();
  };

  if (error) {
    return (
      <Box>
        <Typography color="error">
          Failed to load dashboard data. Please try again later.
        </Typography>
      </Box>
    );
  }

  return (
    <Box>
      {/* Header */}
      <Box display="flex" justifyContent="space-between" alignItems="center" mb={3}>
        <Typography variant="h4" component="h1">
          Incident Dashboard
        </Typography>
        <IconButton onClick={handleRefresh} color="primary">
          <Refresh />
        </IconButton>
      </Box>

      {/* Active Incidents Banner */}
      {metrics && metrics.activeP0Incidents > 0 && (
        <ActiveIncidentsBanner count={metrics.activeP0Incidents} />
      )}

      {/* Metrics Cards */}
      <Grid container spacing={3} mb={3}>
        <Grid item xs={12} sm={6} md={3}>
          <MetricCard
            title="Total Incidents"
            value={isLoading ? <Skeleton /> : metrics?.totalIncidents || 0}
            icon={<Warning />}
            color="primary"
            trend={metrics?.totalIncidentsTrend}
          />
        </Grid>
        <Grid item xs={12} sm={6} md={3}>
          <MetricCard
            title="Active Incidents"
            value={isLoading ? <Skeleton /> : metrics?.activeIncidents || 0}
            icon={<BugReport />}
            color="error"
            subtitle={`P0: ${metrics?.activeP0Incidents || 0}, P1: ${
              metrics?.activeP1Incidents || 0
            }`}
          />
        </Grid>
        <Grid item xs={12} sm={6} md={3}>
          <MetricCard
            title="Avg Resolution Time"
            value={
              isLoading ? (
                <Skeleton />
              ) : (
                `${metrics?.avgResolutionTime || 0} min`
              )
            }
            icon={<Schedule />}
            color="warning"
            trend={metrics?.resolutionTimeTrend}
          />
        </Grid>
        <Grid item xs={12} sm={6} md={3}>
          <MetricCard
            title="Resolved Today"
            value={isLoading ? <Skeleton /> : metrics?.resolvedToday || 0}
            icon={<CheckCircle />}
            color="success"
            trend={metrics?.resolvedTodayTrend}
          />
        </Grid>
      </Grid>

      {/* Charts Row */}
      <Grid container spacing={3} mb={3}>
        <Grid item xs={12} md={6}>
          <Paper sx={{ p: 2, height: '100%' }}>
            <Typography variant="h6" gutterBottom>
              Incident Status Distribution
            </Typography>
            {isLoading ? (
              <Skeleton variant="rectangular" height={300} />
            ) : (
              <IncidentStatusChart data={metrics?.statusDistribution || []} />
            )}
          </Paper>
        </Grid>
        <Grid item xs={12} md={6}>
          <Paper sx={{ p: 2, height: '100%' }}>
            <Typography variant="h6" gutterBottom>
              Severity Distribution
            </Typography>
            {isLoading ? (
              <Skeleton variant="rectangular" height={300} />
            ) : (
              <SeverityDistributionChart
                data={metrics?.severityDistribution || []}
              />
            )}
          </Paper>
        </Grid>
      </Grid>

      {/* Recent Incidents and Timeline */}
      <Grid container spacing={3}>
        <Grid item xs={12} lg={8}>
          <Paper sx={{ p: 2 }}>
            <Typography variant="h6" gutterBottom>
              Recent Incidents
            </Typography>
            {isLoading ? (
              <Skeleton variant="rectangular" height={400} />
            ) : (
              <RecentIncidents incidents={metrics?.recentIncidents || []} />
            )}
          </Paper>
        </Grid>
        <Grid item xs={12} lg={4}>
          <Paper sx={{ p: 2, height: '100%' }}>
            <Typography variant="h6" gutterBottom>
              Activity Timeline
            </Typography>
            {isLoading ? (
              <Skeleton variant="rectangular" height={400} />
            ) : (
              <IncidentTimeline events={metrics?.recentEvents || []} />
            )}
          </Paper>
        </Grid>
      </Grid>
    </Box>
  );
};

export default Dashboard;