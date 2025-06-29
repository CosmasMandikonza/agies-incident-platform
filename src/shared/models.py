"""Data models for Aegis platform."""

from datetime import datetime
from enum import Enum
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field, validator
from aegis_shared.constants import (
    STATUS_OPEN,
    STATUS_ACKNOWLEDGED,
    STATUS_MITIGATING,
    STATUS_RESOLVED,
    STATUS_CLOSED,
    SEVERITY_P0,
    SEVERITY_P1,
    SEVERITY_P2,
    SEVERITY_P3,
    SEVERITY_P4
)


class IncidentStatus(str, Enum):
    """Incident status enumeration."""
    OPEN = STATUS_OPEN
    ACKNOWLEDGED = STATUS_ACKNOWLEDGED
    MITIGATING = STATUS_MITIGATING
    RESOLVED = STATUS_RESOLVED
    CLOSED = STATUS_CLOSED


class Severity(str, Enum):
    """Incident severity enumeration."""
    P0 = SEVERITY_P0
    P1 = SEVERITY_P1
    P2 = SEVERITY_P2
    P3 = SEVERITY_P3
    P4 = SEVERITY_P4


class NotificationType(str, Enum):
    """Notification type enumeration."""
    SLACK = "SLACK"
    EMAIL = "EMAIL"
    PAGE = "PAGE"
    SMS = "SMS"


class BaseEntity(BaseModel):
    """Base model for all entities."""
    
    class Config:
        """Pydantic configuration."""
        use_enum_values = True
        json_encoders = {
            datetime: lambda v: v.isoformat() if v else None
        }


class Incident(BaseEntity):
    """Incident data model."""
    id: str = Field(..., description="Unique incident identifier")
    title: str = Field(..., min_length=1, max_length=200)
    description: Optional[str] = Field(None, max_length=2000)
    status: IncidentStatus = Field(default=IncidentStatus.OPEN)
    severity: Severity
    source: str = Field(..., description="Source of the incident")
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
    acknowledged_at: Optional[datetime] = None
    resolved_at: Optional[datetime] = None
    closed_at: Optional[datetime] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)
    
    @validator('id')
    def validate_id(cls, v):
        """Validate incident ID format."""
        if not v.startswith('INC-'):
            raise ValueError('Incident ID must start with INC-')
        return v
    
    def to_dynamodb_item(self) -> Dict[str, Any]:
        """Convert to DynamoDB item format."""
        return {
            'PK': f'INCIDENT#{self.id}',
            'SK': 'METADATA',
            'GSI1PK': f'STATUS#{self.status}',
            'GSI1SK': f'SEVERITY#{self.severity}#INCIDENT#{self.id}',
            'id': self.id,
            'title': self.title,
            'description': self.description,
            'status': self.status,
            'severity': self.severity,
            'source': self.source,
            'created_at': self.created_at.isoformat(),
            'updated_at': self.updated_at.isoformat(),
            'acknowledged_at': self.acknowledged_at.isoformat() if self.acknowledged_at else None,
            'resolved_at': self.resolved_at.isoformat() if self.resolved_at else None,
            'closed_at': self.closed_at.isoformat() if self.closed_at else None,
            'metadata': self.metadata
        }


class TimelineEvent(BaseEntity):
    """Timeline event data model."""
    incident_id: str
    event_id: str
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    type: str
    description: str
    source: str
    metadata: Dict[str, Any] = Field(default_factory=dict)
    
    def to_dynamodb_item(self) -> Dict[str, Any]:
        """Convert to DynamoDB item format."""
        return {
            'PK': f'INCIDENT#{self.incident_id}',
            'SK': f'EVENT#{self.timestamp.isoformat()}#{self.event_id}',
            'incident_id': self.incident_id,
            'event_id': self.event_id,
            'timestamp': self.timestamp.isoformat(),
            'type': self.type,
            'description': self.description,
            'source': self.source,
            'metadata': self.metadata
        }


class Comment(BaseEntity):
    """Comment data model."""
    incident_id: str
    comment_id: str
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    author_id: str
    author_name: str
    text: str = Field(..., min_length=1, max_length=1000)
    
    def to_dynamodb_item(self) -> Dict[str, Any]:
        """Convert to DynamoDB item format."""
        return {
            'PK': f'INCIDENT#{self.incident_id}',
            'SK': f'COMMENT#{self.timestamp.isoformat()}',
            'incident_id': self.incident_id,
            'comment_id': self.comment_id,
            'timestamp': self.timestamp.isoformat(),
            'author_id': self.author_id,
            'author_name': self.author_name,
            'text': self.text
        }


class Participant(BaseEntity):
    """Participant data model."""
    incident_id: str
    user_id: str
    name: str
    role: str
    joined_at: datetime = Field(default_factory=datetime.utcnow)
    
    def to_dynamodb_item(self) -> Dict[str, Any]:
        """Convert to DynamoDB item format."""
        return {
            'PK': f'INCIDENT#{self.incident_id}',
            'SK': f'USER#{self.user_id}',
            'GSI2PK': f'USER#{self.user_id}',
            'GSI2SK': f'INCIDENT#{self.incident_id}',
            'incident_id': self.incident_id,
            'user_id': self.user_id,
            'name': self.name,
            'role': self.role,
            'joined_at': self.joined_at.isoformat()
        }


class AISummary(BaseEntity):
    """AI-generated summary data model."""
    incident_id: str
    summary_id: str
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    summary_text: str
    model_id: str
    prompt_tokens: Optional[int] = None
    completion_tokens: Optional[int] = None
    
    def to_dynamodb_item(self) -> Dict[str, Any]:
        """Convert to DynamoDB item format."""
        return {
            'PK': f'INCIDENT#{self.incident_id}',
            'SK': f'SUMMARY#{self.timestamp.isoformat()}',
            'incident_id': self.incident_id,
            'summary_id': self.summary_id,
            'timestamp': self.timestamp.isoformat(),
            'summary_text': self.summary_text,
            'model_id': self.model_id,
            'prompt_tokens': self.prompt_tokens,
            'completion_tokens': self.completion_tokens
        }


class NotificationRequest(BaseEntity):
    """Notification request data model."""
    notification_id: str
    incident_id: str
    type: NotificationType
    target: str  # Channel, email, phone number, etc.
    message: str
    priority: str = "normal"
    metadata: Dict[str, Any] = Field(default_factory=dict)
    created_at: datetime = Field(default_factory=datetime.utcnow)
    
    @validator('priority')
    def validate_priority(cls, v):
        """Validate priority value."""
        if v not in ['low', 'normal', 'high', 'critical']:
            raise ValueError('Invalid priority value')
        return v


class CreateIncidentInput(BaseEntity):
    """Input model for creating an incident."""
    title: str = Field(..., min_length=1, max_length=200)
    description: Optional[str] = Field(None, max_length=2000)
    severity: Severity
    source: str
    metadata: Dict[str, Any] = Field(default_factory=dict)


class UpdateIncidentStatusInput(BaseEntity):
    """Input model for updating incident status."""
    status: IncidentStatus
    reason: Optional[str] = None


class EventBridgeEvent(BaseEntity):
    """EventBridge event model."""
    version: str = "0"
    id: str
    detail_type: str = Field(alias="detail-type")
    source: str
    account: str
    time: str
    region: str
    resources: List[str] = Field(default_factory=list)
    detail: Dict[str, Any]