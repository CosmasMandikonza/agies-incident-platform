"""Shared constants for the Aegis platform."""

# Event Sources
EVENT_SOURCE_INCIDENTS = "aegis.incidents"
EVENT_SOURCE_NOTIFICATIONS = "aegis.notifications"
EVENT_SOURCE_WORKFLOW = "aegis.workflow"

# Event Detail Types
EVENT_TYPE_INCIDENT_DECLARED = "Incident Declared"
EVENT_TYPE_TIMELINE_EVENT_ADDED = "Timeline Event Added"
EVENT_TYPE_AI_SUMMARY_GENERATED = "AI Summary Generated"
EVENT_TYPE_INCIDENT_RESOLVED = "Incident Resolved"
EVENT_TYPE_STATUS_CHANGED = "Incident Status Changed"

# DynamoDB Entity Types
ENTITY_TYPE_INCIDENT = "INCIDENT"

# Incident Statuses
STATUS_OPEN = "OPEN"
STATUS_ACKNOWLEDGED = "ACKNOWLEDGED"
STATUS_MITIGATING = "MITIGATING"
STATUS_RESOLVED = "RESOLVED"
STATUS_CLOSED = "CLOSED"

# Incident Severities
SEVERITY_P0 = "P0"
SEVERITY_P1 = "P1"
SEVERITY_P2 = "P2"
SEVERITY_P3 = "P3"
SEVERITY_P4 = "P4"