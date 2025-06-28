#!/bin/bash
set -euo pipefail

# Colors for output
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

echo -e "${GREEN}Building Lambda Layers...${NC}"

# Get the directory of this script
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
cd "$SCRIPT_DIR"

# Clean previous builds
echo "Cleaning previous builds..."
rm -rf powertools/python shared/python

# Build Powertools Layer
echo -e "${YELLOW}Building Powertools Layer...${NC}"
mkdir -p powertools/python
cd powertools

# Create requirements file for powertools
cat > requirements.txt <<EOF
aws-lambda-powertools[all]==2.34.0
EOF

# Install dependencies
pip install -r requirements.txt -t python/ --no-cache-dir

# Clean up unnecessary files
find python -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
find python -type f -name "*.pyc" -delete 2>/dev/null || true
find python -type f -name "*.pyo" -delete 2>/dev/null || true
find python -type d -name "*.dist-info" -exec rm -rf {} + 2>/dev/null || true
find python -type d -name "tests" -exec rm -rf {} + 2>/dev/null || true

cd ..

# Build Shared Libraries Layer
echo -e "${YELLOW}Building Shared Libraries Layer...${NC}"
mkdir -p shared/python
cd shared

# Create shared utilities
mkdir -p python/aegis_shared

# Create __init__.py
cat > python/aegis_shared/__init__.py <<EOF
"""Aegis shared utilities and constants."""
from .constants import *
from .exceptions import *
from .utils import *

__version__ = "1.0.0"
EOF

# Create constants.py
cat > python/aegis_shared/constants.py <<EOF
"""Shared constants for Aegis platform."""

# Event sources
EVENT_SOURCE_INCIDENTS = "aegis.incidents"
EVENT_SOURCE_WORKFLOW = "aegis.workflow"
EVENT_SOURCE_NOTIFICATIONS = "aegis.notifications"

# Event detail types
EVENT_TYPE_INCIDENT_DECLARED = "Incident Declared"
EVENT_TYPE_INCIDENT_ACKNOWLEDGED = "Incident Acknowledged"
EVENT_TYPE_INCIDENT_ESCALATED = "Incident Escalated"
EVENT_TYPE_INCIDENT_RESOLVED = "Incident Resolved"
EVENT_TYPE_TIMELINE_EVENT_ADDED = "Timeline Event Added"
EVENT_TYPE_COMMENT_ADDED = "Comment Added"
EVENT_TYPE_NOTIFICATION_SENT = "Notification Sent"
EVENT_TYPE_AI_SUMMARY_GENERATED = "AI Summary Generated"

# Incident statuses
STATUS_OPEN = "OPEN"
STATUS_ACKNOWLEDGED = "ACKNOWLEDGED"
STATUS_MITIGATING = "MITIGATING"
STATUS_RESOLVED = "RESOLVED"
STATUS_CLOSED = "CLOSED"

# Severity levels
SEVERITY_P0 = "P0"
SEVERITY_P1 = "P1"
SEVERITY_P2 = "P2"
SEVERITY_P3 = "P3"
SEVERITY_P4 = "P4"

# DynamoDB entity types
ENTITY_TYPE_INCIDENT = "INCIDENT"
ENTITY_TYPE_TIMELINE = "TIMELINE"
ENTITY_TYPE_COMMENT = "COMMENT"
ENTITY_TYPE_PARTICIPANT = "PARTICIPANT"
ENTITY_TYPE_AI_SUMMARY = "AI_SUMMARY"

# Notification types
NOTIFICATION_TYPE_SLACK = "SLACK"
NOTIFICATION_TYPE_EMAIL = "EMAIL"
NOTIFICATION_TYPE_PAGE = "PAGE"
NOTIFICATION_TYPE_SMS = "SMS"

# Time constants
DEFAULT_TIMEOUT_SECONDS = 300
DEFAULT_TTL_DAYS = 90
DEFAULT_RETENTION_DAYS = 30

# Pagination
DEFAULT_PAGE_SIZE = 20
MAX_PAGE_SIZE = 100
EOF

# Create exceptions.py
cat > python/aegis_shared/exceptions.py <<EOF
"""Custom exceptions for Aegis platform."""

class AegisError(Exception):
    """Base exception for all Aegis errors."""
    pass

class IncidentNotFoundError(AegisError):
    """Raised when an incident is not found."""
    pass

class InvalidIncidentStateError(AegisError):
    """Raised when an invalid state transition is attempted."""
    pass

class NotificationError(AegisError):
    """Raised when notification sending fails."""
    pass

class ValidationError(AegisError):
    """Raised when input validation fails."""
    pass

class AuthorizationError(AegisError):
    """Raised when authorization fails."""
    pass

class ExternalServiceError(AegisError):
    """Raised when an external service call fails."""
    pass

class AIServiceError(AegisError):
    """Raised when AI service operations fail."""
    pass
EOF

# Create utils.py
cat > python/aegis_shared/utils.py <<EOF
"""Shared utility functions for Aegis platform."""

import json
import os
from datetime import datetime, timezone
from typing import Any, Dict, Optional
import boto3
from botocore.exceptions import ClientError

def get_env_variable(name: str, default: Optional[str] = None) -> str:
    """Get environment variable with optional default."""
    value = os.environ.get(name, default)
    if value is None:
        raise ValueError(f"Environment variable {name} is not set")
    return value

def generate_id(prefix: str) -> str:
    """Generate a unique ID with prefix."""
    from uuid import uuid4
    return f"{prefix}#{str(uuid4())}"

def get_current_timestamp() -> str:
    """Get current ISO format timestamp."""
    return datetime.now(timezone.utc).isoformat()

def parse_entity_id(entity_id: str) -> tuple[str, str]:
    """Parse entity ID into type and UUID."""
    parts = entity_id.split("#", 1)
    if len(parts) != 2:
        raise ValueError(f"Invalid entity ID format: {entity_id}")
    return parts[0], parts[1]

def build_incident_pk(incident_id: str) -> str:
    """Build partition key for incident."""
    return f"INCIDENT#{incident_id}"

def build_timeline_sk(timestamp: str, event_id: str) -> str:
    """Build sort key for timeline event."""
    return f"EVENT#{timestamp}#{event_id}"

def build_comment_sk(timestamp: str) -> str:
    """Build sort key for comment."""
    return f"COMMENT#{timestamp}"

def build_participant_sk(user_id: str) -> str:
    """Build sort key for participant."""
    return f"USER#{user_id}"

def build_ai_summary_sk(timestamp: str) -> str:
    """Build sort key for AI summary."""
    return f"SUMMARY#{timestamp}"

def serialize_for_dynamodb(data: Dict[str, Any]) -> Dict[str, Any]:
    """Serialize data for DynamoDB storage."""
    from decimal import Decimal
    
    def convert(obj):
        if isinstance(obj, float):
            return Decimal(str(obj))
        elif isinstance(obj, dict):
            return {k: convert(v) for k, v in obj.items()}
        elif isinstance(obj, list):
            return [convert(item) for item in obj]
        return obj
    
    return convert(data)

def deserialize_from_dynamodb(data: Dict[str, Any]) -> Dict[str, Any]:
    """Deserialize data from DynamoDB storage."""
    from decimal import Decimal
    
    def convert(obj):
        if isinstance(obj, Decimal):
            return float(obj)
        elif isinstance(obj, dict):
            return {k: convert(v) for k, v in obj.items()}
        elif isinstance(obj, list):
            return [convert(item) for item in obj]
        return obj
    
    return convert(data)

def create_response(
    status_code: int,
    body: Any,
    headers: Optional[Dict[str, str]] = None
) -> Dict[str, Any]:
    """Create API Gateway response."""
    default_headers = {
        "Content-Type": "application/json",
        "Access-Control-Allow-Origin": "*",
        "Access-Control-Allow-Headers": "Content-Type,X-Amz-Date,Authorization,X-Api-Key,X-Amz-Security-Token",
        "Access-Control-Allow-Methods": "GET,POST,PUT,DELETE,OPTIONS"
    }
    
    if headers:
        default_headers.update(headers)
    
    return {
        "statusCode": status_code,
        "headers": default_headers,
        "body": json.dumps(body) if not isinstance(body, str) else body
    }

def get_secret(secret_name: str) -> Dict[str, Any]:
    """Retrieve secret from AWS Secrets Manager."""
    client = boto3.client("secretsmanager")
    
    try:
        response = client.get_secret_value(SecretId=secret_name)
        return json.loads(response["SecretString"])
    except ClientError as e:
        raise ExternalServiceError(f"Failed to retrieve secret {secret_name}: {str(e)}")

def publish_event(
    event_bus_name: str,
    source: str,
    detail_type: str,
    detail: Dict[str, Any]
) -> None:
    """Publish event to EventBridge."""
    client = boto3.client("events")
    
    try:
        client.put_events(
            Entries=[
                {
                    "Source": source,
                    "DetailType": detail_type,
                    "Detail": json.dumps(detail),
                    "EventBusName": event_bus_name
                }
            ]
        )
    except ClientError as e:
        raise ExternalServiceError(f"Failed to publish event: {str(e)}")
EOF

# Add boto3 stubs for better development experience
cat > python/aegis_shared/py.typed <<EOF
# Marker file for PEP 561
EOF

cd ..

echo -e "${GREEN}Lambda layers built successfully!${NC}"
echo "Layers created:"
echo "  - powertools/ (AWS Lambda Powertools)"
echo "  - shared/ (Shared utilities and constants)"