"""Custom exceptions for the Aegis platform."""

class AegisError(Exception):
    """Base exception for the application."""
    pass

class ValidationError(AegisError):
    """For data validation errors."""
    pass

class IncidentNotFoundError(AegisError):
    """When an incident is not found in the database."""
    pass

class AIServiceError(AegisError):
    """For errors related to the AI service (Bedrock)."""
    pass

class ExternalServiceError(AegisError):
    """For errors communicating with external services like Slack."""
    pass