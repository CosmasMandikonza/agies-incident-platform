import React, { useState, useEffect } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import {
  Box,
  Grid,
  Paper,
  Typography,
  Button,
  Chip,
  IconButton,
  Divider,
  Tab,
  Tabs,
  Dialog,
  DialogTitle,
  DialogContent,
  DialogActions,
  TextField,
  Select,
  MenuItem,
  FormControl,
  InputLabel,
  Alert,
  Skeleton,
  Tooltip,
} from '@mui/material';
import {
  ArrowBack,
  Edit,
  CheckCircle,
  Cancel,
  Schedule,
  People,
  Timeline as TimelineIcon,
  Comment as CommentIcon,
  AutoAwesome,
  Share,
  Print,
  Refresh,
} from '@mui/icons-material';
import { useQuery, useMutation, useQueryClient } from 'react-query';
import { format } from 'date-fns';

// Services
import { incidentService } from '@/services/incidentService';

// Components
import IncidentTimeline from '@/components/IncidentDetail/IncidentTimeline';
import IncidentChat from '@/components/IncidentDetail/IncidentChat';
import ParticipantsList from '@/components/IncidentDetail/ParticipantsList';
import AISummaries from '@/components/IncidentDetail/AISummaries';
import StatusChip from '@/components/common/StatusChip';
import SeverityChip from '@/components/common/SeverityChip';

// Hooks
import { useRealTimeUpdates } from '@/hooks/useRealTimeUpdates';
import { useAuth } from '@/contexts/AuthContext';
import { useNotificationContext } from '@/contexts/NotificationContext';

// Types
import { Incident, IncidentStatus } from '@/types';

// Constants
const TABS = {
  TIMELINE: 0,
  CHAT: 1,
  PARTICIPANTS: 2,
  AI_INSIGHTS: 3,
};

const IncidentDetail: React.FC = () => {
  const { incidentId } = useParams<{ incidentId: string }>();
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const { user } = useAuth();
  const { addNotification } = useNotificationContext();
  const { subscribeToIncident } = useRealTimeUpdates();

  const [activeTab, setActiveTab] = useState(TABS.TIMELINE);
  const [statusDialogOpen, setStatusDialogOpen] = useState(false);
  const [newStatus, setNewStatus] = useState<IncidentStatus | ''>('');
  const [statusReason, setStatusReason] = useState('');

  // Fetch incident data
  const {
    data: incident,
    isLoading,
    error,
    refetch,
  } = useQuery<Incident>(
    ['incident', incidentId],
    () => incidentService.getIncident(incidentId!),
    {
      enabled: !!incidentId,
      refetchInterval: 30000, // Refresh every 30 seconds
    }
  );

  // Subscribe to real-time updates
  useEffect(() => {
    if (incidentId) {
      const unsubscribe = subscribeToIncident(incidentId);
      return unsubscribe;
    }
  }, [incidentId, subscribeToIncident]);

  // Status update mutation
  const updateStatusMutation = useMutation(
    (data: { status: IncidentStatus; reason?: string }) =>
      incidentService.updateStatus(incidentId!, data.status, data.reason),
    {
      onSuccess: () => {
        queryClient.invalidateQueries(['incident', incidentId]);
        addNotification({
          type: 'success',
          title: 'Status Updated',
          message: `Incident status changed to ${newStatus}`,
        });
        setStatusDialogOpen(false);
        setNewStatus('');
        setStatusReason('');
      },
      onError: (error: any) => {
        addNotification({
          type: 'error',
          title: 'Update Failed',
          message: error.message || 'Failed to update incident status',
        });
      },
    }
  );

  // Acknowledge mutation
  const acknowledgeMutation = useMutation(
    () => incidentService.acknowledgeIncident(incidentId!),
    {
      onSuccess: () => {
        queryClient.invalidateQueries(['incident', incidentId]);
        addNotification({
          type: 'success',
          title: 'Incident Acknowledged',
          message: 'You have acknowledged this incident',
        });
      },
    }
  );

  // Generate AI summary mutation
  const generateSummaryMutation = useMutation(
    () => incidentService.generateSummary(incidentId!),
    {
      onSuccess: () => {
        addNotification({
          type: 'info',
          title: 'AI Summary Requested',
          message: 'AI is generating a summary for this incident',
        });
      },
    }
  );

  const handleStatusUpdate = () => {
    if (newStatus) {
      updateStatusMutation.mutate({
        status: newStatus as IncidentStatus,
        reason: statusReason,
      });
    }
  };

  const handleExport = async () => {
    try {
      const blob = await incidentService.exportReport(incidentId!, 'pdf');
      const url = window.URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = `incident-${incidentId}-report.pdf`;
      document.body.appendChild(a);
      a.click();
      window.URL.revokeObjectURL(url);
      document.body.removeChild(a);
    } catch (error) {
      addNotification({
        type: 'error',
        title: 'Export Failed',
        message: 'Failed to export incident report',
      });
    }
  };

  if (error) {
    return (
      <Box>
        <Alert severity="error">
          Failed to load incident details. Please try again.
        </Alert>
      </Box>
    );
  }

  if (isLoading || !incident) {
    return (
      <Box>
        <Skeleton variant="text" height={40} width={200} />
        <Skeleton variant="rectangular" height={400} sx={{ mt: 2 }} />
      </Box>
    );
  }

  const canAcknowledge =
    incident.status === IncidentStatus.OPEN &&
    !incident.acknowledgedAt;

  const canResolve = [
    IncidentStatus.ACKNOWLEDGED,
    IncidentStatus.MITIGATING,
  ].includes(incident.status);

  const canClose = incident.status === IncidentStatus.RESOLVED;

  return (
    <Box>
      {/* Header */}
      <Box display="flex" alignItems="center" mb={3}>
        <IconButton onClick={() => navigate('/incidents')} sx={{ mr: 2 }}>
          <ArrowBack />
        </IconButton>
        <Box flex={1}>
          <Typography variant="h4" gutterBottom>
            {incident.title}
          </Typography>
          <Box display="flex" alignItems="center" gap={2}>
            <StatusChip status={incident.status} />
            <SeverityChip severity={incident.severity} />
            <Typography variant="body2" color="textSecondary">
              Created {format(new Date(incident.createdAt), 'PPp')}
            </Typography>
          </Box>
        </Box>
        <Box display="flex" gap={1}>
          <Tooltip title="Refresh">
            <IconButton onClick={() => refetch()}>
              <Refresh />
            </IconButton>
          </Tooltip>
          <Tooltip title="Export Report">
            <IconButton onClick={handleExport}>
              <Print />
            </IconButton>
          </Tooltip>
          <Tooltip title="Share">
            <IconButton>
              <Share />
            </IconButton>
          </Tooltip>
        </Box>
      </Box>

      {/* Quick Actions */}
      <Paper sx={{ p: 2, mb: 3 }}>
        <Box display="flex" gap={2} flexWrap="wrap">
          {canAcknowledge && (
            <Button
              variant="contained"
              color="warning"
              startIcon={<CheckCircle />}
              onClick={() => acknowledgeMutation.mutate()}
              disabled={acknowledgeMutation.isLoading}
            >
              Acknowledge
            </Button>
          )}
          {canResolve && (
            <Button
              variant="contained"
              color="success"
              startIcon={<CheckCircle />}
              onClick={() => {
                setNewStatus(IncidentStatus.RESOLVED);
                setStatusDialogOpen(true);
              }}
            >
              Resolve
            </Button>
          )}
          {canClose && (
            <Button
              variant="outlined"
              startIcon={<Cancel />}
              onClick={() => {
                setNewStatus(IncidentStatus.CLOSED);
                setStatusDialogOpen(true);
              }}
            >
              Close
            </Button>
          )}
          <Button
            variant="outlined"
            startIcon={<Edit />}
            onClick={() => setStatusDialogOpen(true)}
          >
            Update Status
          </Button>
          <Button
            variant="outlined"
            startIcon={<AutoAwesome />}
            onClick={() => generateSummaryMutation.mutate()}
            disabled={generateSummaryMutation.isLoading}
          >
            Generate AI Summary
          </Button>
        </Box>
      </Paper>

      {/* Description */}
      {incident.description && (
        <Paper sx={{ p: 2, mb: 3 }}>
          <Typography variant="h6" gutterBottom>
            Description
          </Typography>
          <Typography variant="body1">{incident.description}</Typography>
        </Paper>
      )}

      {/* Tabs */}
      <Paper sx={{ mb: 3 }}>
        <Tabs
          value={activeTab}
          onChange={(_, value) => setActiveTab(value)}
          variant="fullWidth"
        >
          <Tab
            icon={<TimelineIcon />}
            label="Timeline"
            iconPosition="start"
          />
          <Tab icon={<CommentIcon />} label="Chat" iconPosition="start" />
          <Tab icon={<People />} label="Participants" iconPosition="start" />
          <Tab
            icon={<AutoAwesome />}
            label="AI Insights"
            iconPosition="start"
          />
        </Tabs>
      </Paper>

      {/* Tab Content */}
      <Paper sx={{ p: 2 }}>
        {activeTab === TABS.TIMELINE && (
          <IncidentTimeline
            incidentId={incidentId!}
            timeline={incident.timeline || []}
          />
        )}
        {activeTab === TABS.CHAT && (
          <IncidentChat incidentId={incidentId!} />
        )}
        {activeTab === TABS.PARTICIPANTS && (
          <ParticipantsList
            incidentId={incidentId!}
            participants={incident.participants || []}
          />
        )}
        {activeTab === TABS.AI_INSIGHTS && (
          <AISummaries
            incidentId={incidentId!}
            summaries={incident.aiSummaries || []}
          />
        )}
      </Paper>

      {/* Status Update Dialog */}
      <Dialog
        open={statusDialogOpen}
        onClose={() => setStatusDialogOpen(false)}
        maxWidth="sm"
        fullWidth
      >
        <DialogTitle>Update Incident Status</DialogTitle>
        <DialogContent>
          <FormControl fullWidth sx={{ mt: 2 }}>
            <InputLabel>New Status</InputLabel>
            <Select
              value={newStatus}
              onChange={(e) => setNewStatus(e.target.value as IncidentStatus)}
              label="New Status"
            >
              <MenuItem value={IncidentStatus.ACKNOWLEDGED}>
                Acknowledged
              </MenuItem>
              <MenuItem value={IncidentStatus.MITIGATING}>
                Mitigating
              </MenuItem>
              <MenuItem value={IncidentStatus.RESOLVED}>Resolved</MenuItem>
              <MenuItem value={IncidentStatus.CLOSED}>Closed</MenuItem>
            </Select>
          </FormControl>
          <TextField
            fullWidth
            multiline
            rows={3}
            label="Reason (optional)"
            value={statusReason}
            onChange={(e) => setStatusReason(e.target.value)}
            sx={{ mt: 2 }}
          />
        </DialogContent>
        <DialogActions>
          <Button onClick={() => setStatusDialogOpen(false)}>Cancel</Button>
          <Button
            onClick={handleStatusUpdate}
            variant="contained"
            disabled={!newStatus || updateStatusMutation.isLoading}
          >
            Update
          </Button>
        </DialogActions>
      </Dialog>
    </Box>
  );
};

export default IncidentDetail;