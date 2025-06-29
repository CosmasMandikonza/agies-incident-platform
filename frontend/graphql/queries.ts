import gql from 'graphql-tag';

// Fragments
export const INCIDENT_FIELDS = gql`
  fragment IncidentFields on Incident {
    id
    title
    description
    status
    severity
    createdAt
    updatedAt
    acknowledgedAt
    resolvedAt
  }
`;

export const TIMELINE_EVENT_FIELDS = gql`
  fragment TimelineEventFields on TimelineEvent {
    id
    timestamp
    type
    description
    source
    metadata
  }
`;

export const PARTICIPANT_FIELDS = gql`
  fragment ParticipantFields on Participant {
    userId
    name
    role
    joinedAt
  }
`;

// Queries
export const GET_INCIDENT = gql`
  ${INCIDENT_FIELDS}
  ${TIMELINE_EVENT_FIELDS}
  ${PARTICIPANT_FIELDS}
  query GetIncident($id: ID!) {
    getIncident(id: $id) {
      ...IncidentFields
      timeline {
        ...TimelineEventFields
      }
      participants {
        ...ParticipantFields
      }
      aiSummaries {
        id
        timestamp
        summary
        modelId
      }
    }
  }
`;

export const LIST_INCIDENTS = gql`
  ${INCIDENT_FIELDS}
  query ListIncidents(
    $status: IncidentStatus
    $severity: Severity
    $limit: Int
    $nextToken: String
  ) {
    listIncidents(
      status: $status
      severity: $severity
      limit: $limit
      nextToken: $nextToken
    ) {
      items {
        ...IncidentFields
      }
      nextToken
    }
  }
`;

export const GET_DASHBOARD_METRICS = gql`
  query GetDashboardMetrics {
    getDashboardMetrics {
      totalIncidents
      activeIncidents
      activeP0Incidents
      activeP1Incidents
      resolvedToday
      avgResolutionTime
      totalIncidentsTrend
      resolutionTimeTrend
      resolvedTodayTrend
      statusDistribution {
        status
        count
      }
      severityDistribution {
        severity
        count
      }
      recentIncidents {
        id
        title
        severity
        status
        createdAt
      }
      recentEvents {
        timestamp
        type
        description
        incidentId
      }
    }
  }
`;

// Mutations
export const CREATE_INCIDENT = gql`
  ${INCIDENT_FIELDS}
  mutation CreateIncident($input: CreateIncidentInput!) {
    createIncident(input: $input) {
      ...IncidentFields
    }
  }
`;

export const UPDATE_INCIDENT_STATUS = gql`
  ${INCIDENT_FIELDS}
  mutation UpdateIncidentStatus($id: ID!, $status: IncidentStatus!) {
    updateIncidentStatus(id: $id, status: $status) {
      ...IncidentFields
    }
  }
`;

export const ADD_COMMENT = gql`
  ${TIMELINE_EVENT_FIELDS}
  mutation AddComment($incidentId: ID!, $text: String!) {
    addComment(incidentId: $incidentId, text: $text) {
      ...TimelineEventFields
    }
  }
`;

// Subscriptions
export const ON_INCIDENT_UPDATE = gql`
  ${INCIDENT_FIELDS}
  subscription OnIncidentUpdate($id: ID!) {
    onIncidentUpdate(id: $id) {
      ...IncidentFields
    }
  }
`;

export const ON_TIMELINE_UPDATE = gql`
  ${TIMELINE_EVENT_FIELDS}
  subscription OnTimelineUpdate($incidentId: ID!) {
    onTimelineUpdate(incidentId: $incidentId) {
      ...TimelineEventFields
    }
  }
`;

export const ON_NEW_INCIDENT = gql`
  ${INCIDENT_FIELDS}
  subscription OnNewIncident {
    onNewIncident {
      ...IncidentFields
    }
  }
`;

export const ON_STATUS_CHANGE = gql`
  subscription OnStatusChange {
    onStatusChange {
      incidentId
      oldStatus
      newStatus
      changedAt
      changedBy
    }
  }
`;