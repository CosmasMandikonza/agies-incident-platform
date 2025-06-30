"""
Incident Ingestor Lambda Function
Receives incident declarations from various sources and normalizes them.
"""

import json
import uuid
from datetime import datetime
from typing import Dict, Any, Optional
from aws_lambda_powertools import Logger, Tracer, Metrics
from aws_lambda_powertools.metrics import MetricUnit
from aws_lambda_powertools.logging import correlation_paths
from aws_lambda_powertools.utilities.typing import LambdaContext
from aws_lambda_powertools.utilities.data_classes import APIGatewayProxyEvent, event_source

# Import shared modules
from shared.config import Config
from shared.models import Incident, TimelineEvent, CreateIncidentInput
from shared.dynamodb_client import DynamoDBClient
from shared.event_publisher import EventPublisher
from shared.validators import validate_incident_input
from shared.constants import (
    EVENT_SOURCE_INCIDENTS,
    EVENT_TYPE_INCIDENT_DECLARED,
    EVENT_TYPE_TIMELINE_EVENT_ADDED,
    ENTITY_TYPE_INCIDENT
)
from shared.exceptions import ValidationError, AegisError
from shared.utils import create_response, generate_id

# Initialize AWS Lambda Powertools
logger = Logger()
tracer = Tracer()
metrics = Metrics()

# Initialize configuration
config = Config()

# Initialize clients
dynamodb_client = DynamoDBClient(config.table_name)
event_publisher = EventPublisher(config.event_bus_name)


@tracer.capture_method
def process_api_gateway_event(event_body: Dict[str, Any]) -> Dict[str, Any]:
    """Process incident creation from API Gateway."""
    logger.info("Processing API Gateway incident creation request")
    
    # Validate input
    validated_input = validate_incident_input(event_body)
    
    # Generate incident ID
    incident_id = generate_id("INC")
    
    # Create incident model
    incident = Incident(
        id=incident_id,
        title=validated_input.title,
        description=validated_input.description,
        severity=validated_input.severity,
        source=validated_input.source,
        metadata=validated_input.metadata
    )
    
    return create_incident(incident)


@tracer.capture_method
def process_cloudwatch_alarm(alarm_event: Dict[str, Any]) -> Dict[str, Any]:
    """Process CloudWatch Alarm state change."""
    logger.info("Processing CloudWatch Alarm event")
    
    # Extract alarm details
    alarm_name = alarm_event.get("AlarmName", "Unknown Alarm")
    alarm_description = alarm_event.get("AlarmDescription", "")
    new_state = alarm_event.get("NewStateValue", "UNKNOWN")
    reason = alarm_event.get("NewStateReason", "")
    
    # Only create incident for ALARM state
    if new_state != "ALARM":
        logger.info(f"Ignoring alarm state: {new_state}")
        return {"message": "Alarm state not actionable"}
    
    # Map CloudWatch alarm to incident
    incident_id = generate_id("INC")
    
    # Determine severity based on alarm name patterns
    severity = "P2"  # Default
    if "critical" in alarm_name.lower() or "p0" in alarm_name.lower():
        severity = "P0"
    elif "high" in alarm_name.lower() or "p1" in alarm_name.lower():
        severity = "P1"
    
    incident = Incident(
        id=incident_id,
        title=f"CloudWatch Alarm: {alarm_name}",
        description=f"{alarm_description}\n\nReason: {reason}",
        severity=severity,
        source="CloudWatch Alarms",
        metadata={
            "alarm_name": alarm_name,
            "alarm_arn": alarm_event.get("AlarmArn"),
            "region": alarm_event.get("Region"),
            "account_id": alarm_event.get("AWSAccountId"),
            "metric_name": alarm_event.get("Trigger", {}).get("MetricName"),
            "namespace": alarm_event.get("Trigger", {}).get("Namespace")
        }
    )
    
    return create_incident(incident)


@tracer.capture_method
def create_incident(incident: Incident) -> Dict[str, Any]:
    """Create incident in DynamoDB and publish events."""
    try:
        # Start a list to track all items to write
        items_to_write = []
        
        # Add incident metadata
        items_to_write.append(incident.to_dynamodb_item())
        
        # Create initial timeline event
        timeline_event = TimelineEvent(
            incident_id=incident.id,
            event_id=str(uuid.uuid4()),
            type="INCIDENT_CREATED",
            description=f"Incident created with severity {incident.severity}",
            source="System",
            metadata={
                "initial_severity": incident.severity,
                "initial_status": incident.status
            }
        )
        items_to_write.append(timeline_event.to_dynamodb_item())
        
        # Write all items to DynamoDB
        dynamodb_client.batch_write_items(items_to_write)
        
        # Publish events to EventBridge
        events_to_publish = []
        
        # Incident declared event
        events_to_publish.append({
            "source": EVENT_SOURCE_INCIDENTS,
            "detail_type": EVENT_TYPE_INCIDENT_DECLARED,
            "detail": {
                "incidentId": incident.id,
                "title": incident.title,
                "severity": incident.severity,
                "status": incident.status,
                "source": incident.source
            }
        })
        
        # Timeline event added
        events_to_publish.append({
            "source": EVENT_SOURCE_INCIDENTS,
            "detail_type": EVENT_TYPE_TIMELINE_EVENT_ADDED,
            "detail": {
                "incidentId": incident.id,
                "eventId": timeline_event.event_id,
                "eventType": timeline_event.type,
                "timestamp": timeline_event.timestamp.isoformat()
            }
        })
        
        event_publisher.publish_batch_events(events_to_publish)
        
        # Emit metrics
        metrics.add_metric(name="IncidentCreated", unit=MetricUnit.Count, value=1)
        metrics.add_metadata(key="severity", value=incident.severity)
        metrics.add_metadata(key="source", value=incident.source)
        
        logger.info(f"Incident {incident.id} created successfully")
        
        return {
            "incidentId": incident.id,
            "title": incident.title,
            "severity": incident.severity,
            "status": incident.status,
            "createdAt": incident.created_at.isoformat()
        }
        
    except Exception as e:
        logger.error(f"Failed to create incident: {str(e)}", exc_info=True)
        metrics.add_metric(name="IncidentCreationFailed", unit=MetricUnit.Count, value=1)
        raise


@logger.inject_lambda_context(correlation_id_path=correlation_paths.API_GATEWAY_REST)
@tracer.capture_lambda_handler
@metrics.log_metrics(capture_cold_start_metric=True)
@event_source(data_class=APIGatewayProxyEvent)
def handler(event: APIGatewayProxyEvent, context: LambdaContext) -> Dict[str, Any]:
    """
    Lambda handler for incident ingestion.
    Supports multiple event sources: API Gateway, CloudWatch Alarms, EventBridge.
    """
    try:
        logger.info("Incident ingestor invoked", extra={
            "request_id": context.request_id,
            "event_source": event.get("source", "api-gateway")
        })
        
        # Handle API Gateway events
        if event.get("httpMethod"):
            # Parse request body
            try:
                body = json.loads(event.get("body", "{}"))
            except json.JSONDecodeError:
                return create_response(400, {"error": "Invalid JSON in request body"})
            
            # Process the incident creation
            try:
                result = process_api_gateway_event(body)
                return create_response(201, result)
            except ValidationError as e:
                return create_response(400, {"error": str(e)})
            except Exception as e:
                logger.error(f"Failed to process request: {str(e)}", exc_info=True)
                return create_response(500, {"error": "Internal server error"})
        
        # Handle CloudWatch Alarm events
        elif event.get("source") == "aws.cloudwatch" and event.get("detail-type") == "CloudWatch Alarm State Change":
            result = process_cloudwatch_alarm(event.get("detail", {}))
            return {"statusCode": 200, "body": json.dumps(result)}
        
        # Handle other EventBridge events
        elif event.get("source"):
            logger.info(f"Received event from source: {event['source']}")
            # Add handling for other event sources as needed
            return {"statusCode": 200, "body": json.dumps({"message": "Event processed"})}
        
        else:
            logger.warning("Unsupported event type")
            return create_response(400, {"error": "Unsupported event type"})
            
    except Exception as e:
        logger.error(f"Unexpected error in handler: {str(e)}", exc_info=True)
        metrics.add_metric(name="HandlerError", unit=MetricUnit.Count, value=1)
        
        if event.get("httpMethod"):
            return create_response(500, {"error": "Internal server error"})
        else:
            raise  # Re-raise for non-API Gateway events