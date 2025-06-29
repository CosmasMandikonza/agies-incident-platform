"""
Validate Input Lambda Function
Validates workflow input for Step Functions.
"""

from typing import Dict, Any
from aws_lambda_powertools import Logger
from aws_lambda_powertools.utilities.typing import LambdaContext

logger = Logger()


def validate_incident_id(incident_id: str) -> bool:
    """Validate incident ID format."""
    if not incident_id:
        return False
    if not incident_id.startswith("INC-"):
        return False
    if len(incident_id) < 10:
        return False
    return True


@logger.inject_lambda_context
def handler(event: Dict[str, Any], context: LambdaContext) -> Dict[str, Any]:
    """
    Validate workflow input.
    """
    logger.info("Validating workflow input", extra={"event": event})
    
    # Check required fields
    incident_id = event.get("incidentId")
    
    if not incident_id:
        raise ValueError("Missing required field: incidentId")
    
    if not validate_incident_id(incident_id):
        raise ValueError(f"Invalid incident ID format: {incident_id}")
    
    # Return validated input
    return {
        "incidentId": incident_id,
        "source": event.get("source", "unknown"),
        "validated": True,
        "validatedAt": context.aws_request_id
    }