"""Input validators for Aegis platform."""

from typing import Dict, Any, Optional
from pydantic import ValidationError
from aws_lambda_powertools import Logger
from .models import CreateIncidentInput, UpdateIncidentStatusInput, Comment
from shared.exceptions import ValidationError as AegisValidationError

logger = Logger()


def validate_incident_input(data: Dict[str, Any]) -> CreateIncidentInput:
    """Validate input for creating an incident."""
    try:
        # Clean and validate input
        validated_input = CreateIncidentInput(**data)
        
        # Additional business rule validations
        if validated_input.severity == "P0" and not validated_input.description:
            raise AegisValidationError("P0 incidents must have a description")
        
        logger.info("Incident input validated successfully", extra={
            "title": validated_input.title,
            "severity": validated_input.severity
        })
        
        return validated_input
        
    except ValidationError as e:
        logger.error("Incident input validation failed", extra={"errors": e.errors()})
        error_messages = [f"{err['loc'][0]}: {err['msg']}" for err in e.errors()]
        raise AegisValidationError(f"Invalid input: {', '.join(error_messages)}")


def validate_status_update(data: Dict[str, Any], current_status: str) -> UpdateIncidentStatusInput:
    """Validate input for updating incident status."""
    try:
        validated_input = UpdateIncidentStatusInput(**data)
        
        # Validate state transitions
        valid_transitions = {
            "OPEN": ["ACKNOWLEDGED", "RESOLVED", "CLOSED"],
            "ACKNOWLEDGED": ["MITIGATING", "RESOLVED", "CLOSED"],
            "MITIGATING": ["RESOLVED", "CLOSED"],
            "RESOLVED": ["CLOSED", "OPEN"],  # Can reopen
            "CLOSED": ["OPEN"]  # Can reopen
        }
        
        if validated_input.status not in valid_transitions.get(current_status, []):
            raise AegisValidationError(
                f"Invalid status transition from {current_status} to {validated_input.status}"
            )
        
        logger.info("Status update validated successfully", extra={
            "current_status": current_status,
            "new_status": validated_input.status
        })
        
        return validated_input
        
    except ValidationError as e:
        logger.error("Status update validation failed", extra={"errors": e.errors()})
        error_messages = [f"{err['loc'][0]}: {err['msg']}" for err in e.errors()]
        raise AegisValidationError(f"Invalid input: {', '.join(error_messages)}")


def validate_comment_input(data: Dict[str, Any]) -> Dict[str, Any]:
    """Validate input for adding a comment."""
    try:
        # Required fields
        if not data.get("text"):
            raise AegisValidationError("Comment text is required")
        
        if not data.get("author_id"):
            raise AegisValidationError("Author ID is required")
        
        if not data.get("author_name"):
            raise AegisValidationError("Author name is required")
        
        # Validate text length
        text = data["text"].strip()
        if len(text) < 1:
            raise AegisValidationError("Comment cannot be empty")
        
        if len(text) > 1000:
            raise AegisValidationError("Comment cannot exceed 1000 characters")
        
        logger.info("Comment input validated successfully")
        
        return {
            "text": text,
            "author_id": data["author_id"],
            "author_name": data["author_name"]
        }
        
    except KeyError as e:
        raise AegisValidationError(f"Missing required field: {str(e)}")


def validate_pagination_params(params: Dict[str, Any]) -> Dict[str, Any]:
    """Validate pagination parameters."""
    validated = {}
    
    # Validate limit
    limit = params.get("limit", 20)
    try:
        limit = int(limit)
        if limit < 1:
            raise ValueError("Limit must be positive")
        if limit > 100:
            limit = 100  # Cap at maximum
        validated["limit"] = limit
    except (ValueError, TypeError):
        raise AegisValidationError("Invalid limit parameter")
    
    # Validate next_token if provided
    if "next_token" in params:
        validated["next_token"] = params["next_token"]
    
    # Validate sort order if provided
    sort_order = params.get("sort_order", "desc")
    if sort_order not in ["asc", "desc"]:
        raise AegisValidationError("Sort order must be 'asc' or 'desc'")
    validated["sort_order"] = sort_order
    
    return validated


def validate_severity(severity: str) -> str:
    """Validate severity value."""
    valid_severities = ["P0", "P1", "P2", "P3", "P4"]
    
    severity = severity.upper()
    if severity not in valid_severities:
        raise AegisValidationError(f"Invalid severity. Must be one of: {', '.join(valid_severities)}")
    
    return severity


def validate_notification_target(notification_type: str, target: str) -> None:
    """Validate notification target based on type."""
    import re
    
    if notification_type == "EMAIL":
        # Basic email validation
        email_pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
        if not re.match(email_pattern, target):
            raise AegisValidationError("Invalid email address")
    
    elif notification_type == "SLACK":
        # Validate Slack channel format
        if not target.startswith("#") and not target.startswith("@"):
            raise AegisValidationError("Slack target must start with # (channel) or @ (user)")
    
    elif notification_type == "SMS":
        # Basic phone number validation (E.164 format)
        phone_pattern = r'^\+[1-9]\d{1,14}$'
        if not re.match(phone_pattern, target):
            raise AegisValidationError("Phone number must be in E.164 format (e.g., +1234567890)")
    
    elif notification_type == "PAGE":
        # PagerDuty service key validation
        if len(target) != 32:
            raise AegisValidationError("Invalid PagerDuty service key")