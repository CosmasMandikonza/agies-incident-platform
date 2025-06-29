// Enums
export enum IncidentStatus {
  OPEN = 'OPEN',
  ACKNOWLEDGED = 'ACKNOWLEDGED',
  MITIGATING = 'MITIGATING',
  RESOLVED = 'RESOLVED',
  CLOSED = 'CLOSED',
}

export enum Severity {
  P0 = 'P0',
  P1 = 'P1',
  P2 = 'P2',
  P3 = 'P3',
  P4 = 'P4',
}

export enum NotificationType {
  SLACK = 'SLACK',
  EMAIL = 'EMAIL',
  PAGE = 'PAGE',
  SMS = 'SMS',
}

export enum TimelineEventType {
  INCIDENT_CREATED = 'INCIDENT_CREATED',
  STATUS_CHANGED = 'STATUS_CHANGED',
  SEVERITY_CHANGED = 'SEVERITY_CHANGED',
  COMMENT_ADDED = 'COMMENT_ADDED',
  USER_JOINED = 'USER_JOINED',
  USER_LEFT = 'USER_LEFT',
  AUTOMATED_TRIAGE = 'AUTOMATED_TRIAGE',
  AI_SUMMARY = 'AI_SUMMARY',
  POST_MORTEM_GENERATED = 'POST_MORTEM_GENERATED',
  NOTIFICATION_SENT = 'NOTIFICATION_SENT',
  ESCALATION = 'ESCALATION',
}

// Interfaces
export interface User {
  id: string;
  email: string;
  name: string;
  role: string;
  attributes?: Record<string, any>;
}

export interface Incident {
  id: string;
  title: string;
  description?: string;
  status: IncidentStatus;
  severity: Severity;
  source: string;
  createdAt: string;
  updatedAt: string;
  acknowledgedAt?: string;
  resolvedAt?: string;
  closedAt?: string;
  metadata?: Record<string, any>;
  timeline?: TimelineEvent[];
  participants?: Participant[];
  aiSummaries?: AISummary[];
}

export interface TimelineEvent {
  id: string;
  timestamp: string;
  type: string;
  description: string;
  source: string;
  metadata?: Record<string, any>;
}

export interface Participant {
  userId: string;
  name: string;
  role: string;
  joinedAt: string;
}

export interface AISummary {
  id: string;
  timestamp: string;
  summary: string;
  modelId: string;
}

export interface Comment {
  id: string;
  incidentId: string;
  timestamp: string;
  authorId: string;
  authorName: string;
  text: string;
}

export interface Notification {
  id: string;
  type: 'info' | 'warning' | 'error' | 'success';
  title: string;
  message: string;
  timestamp: string;
  read: boolean;
  metadata?: {
    incidentId?: string;
    severity?: Severity;
    [key: string]: any;
  };
}

export interface DashboardMetrics {
  totalIncidents: number;
  activeIncidents: number;
  activeP0Incidents: number;
  activeP1Incidents: number;
  resolvedToday: number;
  avgResolutionTime: number; // in minutes
  totalIncidentsTrend?: 'up' | 'down' | 'stable';
  resolutionTimeTrend?: 'up' | 'down' | 'stable';
  resolvedTodayTrend?: 'up' | 'down' | 'stable';
  statusDistribution: StatusDistribution[];
  severityDistribution: SeverityDistribution[];
  recentIncidents: Incident[];
  recentEvents: TimelineEvent[];
}

export interface StatusDistribution {
  status: IncidentStatus;
  count: number;
}

export interface SeverityDistribution {
  severity: Severity;
  count: number;
}

export interface CreateIncidentInput {
  title: string;
  description?: string;
  severity: Severity;
  source: string;
  metadata?: Record<string, any>;
}

export interface UpdateIncidentInput {
  id: string;
  title?: string;
  description?: string;
  status?: IncidentStatus;
  severity?: Severity;
}

export interface PaginationParams {
  limit?: number;
  nextToken?: string;
}

export interface ListIncidentsParams extends PaginationParams {
  status?: IncidentStatus;
  severity?: Severity;
  startDate?: string;
  endDate?: string;
}

export interface IncidentConnection {
  items: Incident[];
  nextToken?: string;
  totalCount?: number;
}

export interface ChartData {
  labels: string[];
  datasets: {
    label: string;
    data: number[];
    backgroundColor?: string | string[];
    borderColor?: string | string[];
    borderWidth?: number;
  }[];
}

export interface FilterOptions {
  statuses: IncidentStatus[];
  severities: Severity[];
  dateRange: {
    start: Date | null;
    end: Date | null;
  };
  searchTerm: string;
}

export interface SortOptions {
  field: 'createdAt' | 'updatedAt' | 'severity' | 'status' | 'title';
  direction: 'asc' | 'desc';
}

export interface AppConfig {
  apiEndpoint: string;
  graphqlEndpoint: string;
  region: string;
  userPoolId: string;
  userPoolClientId: string;
  features: {
    enableAIScribe: boolean;
    enableChaosExperiments: boolean;
    enableAdvancedAnalytics: boolean;
  };
}