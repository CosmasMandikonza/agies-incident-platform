"""
Realtime Propagator Lambda Function
Processes DynamoDB Streams and propagates updates to AppSync for real-time sync.
"""

import json
import os
from typing import Dict, Any, List, Optional
from datetime import datetime
import boto3
import httpx
from aws_lambda_powertools import Logger, Tracer, Metrics
from aws_lambda_powertools.metrics import MetricUnit
from aws_lambda_powertools.utilities.typing import LambdaContext
from aws_lambda_powertools.utilities.data_classes import DynamoDBStreamEvent, event_source
from aws_lambda_powertools.utilities.data_classes.dynamo_db_stream_event import (
    DynamoDBRecordEventName, StreamRecord
)
from botocore.auth import SigV4Auth
from botocore.awsrequest import AWSRequest
import botocore.session

# Import shared modules  
from shared.config import Config
from shared.exceptions import ExternalServiceError

# Initialize AWS Lambda Powertools
logger = Logger()
tracer = Tracer()
metrics = Metrics()

# Initialize configuration
config = Config()


class AppSyncClient:
    """Client for interacting with AWS AppSync."""
    
    def __init__(self, endpoint: str, region: Optional[str] = None):
        """Initialize AppSync client."""
        self.endpoint = endpoint
        self.region = region or config.region
        self.http_client = httpx.Client(timeout=30.0)
        
        # Set up AWS credentials for signing
        session = botocore.session.Session()
        self.credentials = session.get_credentials()
        
        logger.info(f"Initialized AppSync client for endpoint: {endpoint}")
    
    @tracer.capture_method
    def execute_mutation(self, mutation: str, variables: Dict[str, Any]) -> Dict[str, Any]:
        """Execute a GraphQL mutation."""
        try:
            # Prepare the request
            request_body = {
                "query": mutation,
                "variables": variables
            }
            
            # Create and sign the request
            request = AWSRequest(
                method="POST",
                url=self.endpoint,
                data=json.dumps(request_body),
                headers={
                    "Content-Type": "application/json",
                    "Accept": "application/json"
                }
            )
            
            # Sign with SigV4
            SigV4Auth(self.credentials, "appsync", self.region).add_auth(request)
            
            # Convert to httpx format
            headers = dict(request.headers)
            
            # Send the request
            response = self.http_client.post(
                self.endpoint,
                content=request.body,
                headers=headers
            )
            
            if response.status_code != 200:
                raise ExternalServiceError(
                    f"AppSync mutation failed: {response.status_code} - {response.text}"
                )
            
            result = response.json()
            
            if "errors" in result:
                raise ExternalServiceError(f"GraphQL errors: {result['errors']}")
            
            logger.info("AppSync mutation executed successfully")
            return result.get("data", {})
            
        except Exception as e:
            logger.error(f"Failed to execute AppSync mutation: {str(e)}", exc_info=True)
            raise ExternalServiceError(f"AppSync error: {str(e)}")


# Initialize AppSync client
appsync_client = AppSyncClient(config.appsync_endpoint) if config.appsync_endpoint else None


# GraphQL Mutations
UPDATE_INCIDENT_MUTATION = """
mutation UpdateIncident($input: UpdateIncidentInput!) {
  updateIncident(input: $input) {
    id
    status
    updatedAt
  }
}
"""

ADD_TIMELINE_EVENT_MUTATION = """
mutation AddTimelineEvent($input: AddTimelineEventInput!) {
  addTimelineEvent(input: $input) {
    id
    timestamp
    type
  }
}
"""

ADD_COMMENT_MUTATION = """
mutation AddComment($input: AddCommentInput!) {
  addComment(input: $input) {
    id
    timestamp
    text
  }
}
"""

UPDATE_PARTICIPANT_MUTATION = """
mutation UpdateParticipant($input: UpdateParticipantInput!) {
  updateParticipant(input: $input) {
    userId
    role
  }
}
"""


@tracer.capture_method
def process_stream_record(record: StreamRecord, event_name: DynamoDBRecordEventName) -> None:
    """Process a single DynamoDB stream record."""
    # Skip if no AppSync endpoint configured (local testing)
    if not appsync_client:
        logger.info("No AppSync endpoint configured, skipping propagation")
        return
    
    # Extract the new image (current state)
    new_image = record.get("NewImage", {})
    old_image = record.get("OldImage", {})
    
    # Get the keys
    pk = new_image.get("PK", {}).get("S", "")
    sk = new_image.get("SK", {}).get("S", "")
    
    if not pk or not sk:
        logger.warning("Record missing PK or SK, skipping")
        return
    
    # Route based on entity type
    if pk.startswith("INCIDENT#") and sk == "METADATA":
        handle_incident_update(new_image, old_image, event_name)
    elif pk.startswith("INCIDENT#") and sk.startswith("EVENT#"):
        handle_timeline_event(new_image, event_name)
    elif pk.startswith("INCIDENT#") and sk.startswith("COMMENT#"):
        handle_comment(new_image, event_name)
    elif pk.startswith("INCIDENT#") and sk.startswith("USER#"):
        handle_participant_update(new_image, event_name)
    elif pk.startswith("INCIDENT#") and sk.startswith("SUMMARY#"):
        handle_ai_summary(new_image, event_name)
    else:
        logger.debug(f"Unhandled record type: PK={pk}, SK={sk}")


@tracer.capture_method
def handle_incident_update(new_image: Dict, old_image: Dict, event_name: DynamoDBRecordEventName) -> None:
    """Handle incident metadata updates."""
    if event_name == DynamoDBRecordEventName.REMOVE:
        return  # Skip deletions
    
    # Extract incident ID
    incident_id = new_image["PK"]["S"].replace("INCIDENT#", "")
    
    # Prepare update input
    update_input = {
        "id": incident_id,
        "title": new_image.get("title", {}).get("S"),
        "status": new_image.get("status", {}).get("S"),
        "severity": new_image.get("severity", {}).get("S"),
        "updatedAt": new_image.get("updated_at", {}).get("S")
    }
    
    # Check what changed
    if old_image:
        old_status = old_image.get("status", {}).get("S")
        new_status = new_image.get("status", {}).get("S")
        
        if old_status != new_status:
            logger.info(f"Incident {incident_id} status changed: {old_status} -> {new_status}")
            metrics.add_metric(name="StatusChange", unit=MetricUnit.Count, value=1)
            metrics.add_metadata(key="from_status", value=old_status)
            metrics.add_metadata(key="to_status", value=new_status)
    
    # Execute mutation
    try:
        appsync_client.execute_mutation(UPDATE_INCIDENT_MUTATION, {"input": update_input})
        metrics.add_metric(name="IncidentUpdatePropagated", unit=MetricUnit.Count, value=1)
    except Exception as e:
        logger.error(f"Failed to propagate incident update: {str(e)}")
        metrics.add_metric(name="PropagationError", unit=MetricUnit.Count, value=1)


@tracer.capture_method
def handle_timeline_event(new_image: Dict, event_name: DynamoDBRecordEventName) -> None:
    """Handle timeline event additions."""
    if event_name != DynamoDBRecordEventName.INSERT:
        return  # Only handle new events
    
    # Extract data
    incident_id = new_image["PK"]["S"].replace("INCIDENT#", "")
    
    # Prepare input
    event_input = {
        "incidentId": incident_id,
        "eventId": new_image.get("event_id", {}).get("S"),
        "timestamp": new_image.get("timestamp", {}).get("S"),
        "type": new_image.get("type", {}).get("S"),
        "description": new_image.get("description", {}).get("S"),
        "source": new_image.get("source", {}).get("S")
    }
    
    # Execute mutation
    try:
        appsync_client.execute_mutation(ADD_TIMELINE_EVENT_MUTATION, {"input": event_input})
        metrics.add_metric(name="TimelineEventPropagated", unit=MetricUnit.Count, value=1)
    except Exception as e:
        logger.error(f"Failed to propagate timeline event: {str(e)}")
        metrics.add_metric(name="PropagationError", unit=MetricUnit.Count, value=1)


@tracer.capture_method
def handle_comment(new_image: Dict, event_name: DynamoDBRecordEventName) -> None:
    """Handle comment additions."""
    if event_name != DynamoDBRecordEventName.INSERT:
        return  # Only handle new comments
    
    # Extract data
    incident_id = new_image["PK"]["S"].replace("INCIDENT#", "")
    
    # Prepare input
    comment_input = {
        "incidentId": incident_id,
        "commentId": new_image.get("comment_id", {}).get("S"),
        "timestamp": new_image.get("timestamp", {}).get("S"),
        "authorId": new_image.get("author_id", {}).get("S"),
        "authorName": new_image.get("author_name", {}).get("S"),
        "text": new_image.get("text", {}).get("S")
    }
    
    # Execute mutation
    try:
        appsync_client.execute_mutation(ADD_COMMENT_MUTATION, {"input": comment_input})
        metrics.add_metric(name="CommentPropagated", unit=MetricUnit.Count, value=1)
    except Exception as e:
        logger.error(f"Failed to propagate comment: {str(e)}")
        metrics.add_metric(name="PropagationError", unit=MetricUnit.Count, value=1)


@tracer.capture_method
def handle_participant_update(new_image: Dict, event_name: DynamoDBRecordEventName) -> None:
    """Handle participant updates."""
    if event_name == DynamoDBRecordEventName.REMOVE:
        # Handle participant removal
        incident_id = new_image["PK"]["S"].replace("INCIDENT#", "")
        user_id = new_image["SK"]["S"].replace("USER#", "")
        
        logger.info(f"Participant {user_id} removed from incident {incident_id}")
        # Could propagate removal if needed
        return
    
    # Extract data
    incident_id = new_image["PK"]["S"].replace("INCIDENT#", "")
    
    # Prepare input
    participant_input = {
        "incidentId": incident_id,
        "userId": new_image.get("user_id", {}).get("S"),
        "name": new_image.get("name", {}).get("S"),
        "role": new_image.get("role", {}).get("S"),
        "joinedAt": new_image.get("joined_at", {}).get("S")
    }
    
    # Execute mutation
    try:
        appsync_client.execute_mutation(UPDATE_PARTICIPANT_MUTATION, {"input": participant_input})
        metrics.add_metric(name="ParticipantUpdatePropagated", unit=MetricUnit.Count, value=1)
    except Exception as e:
        logger.error(f"Failed to propagate participant update: {str(e)}")
        metrics.add_metric(name="PropagationError", unit=MetricUnit.Count, value=1)


@tracer.capture_method
def handle_ai_summary(new_image: Dict, event_name: DynamoDBRecordEventName) -> None:
    """Handle AI summary additions."""
    if event_name != DynamoDBRecordEventName.INSERT:
        return  # Only handle new summaries
    
    # Extract data
    incident_id = new_image["PK"]["S"].replace("INCIDENT#", "")
    
    logger.info(f"New AI summary added for incident {incident_id}")
    
    # Create a timeline event for the summary
    summary_event_input = {
        "incidentId": incident_id,
        "eventId": new_image.get("summary_id", {}).get("S"),
        "timestamp": new_image.get("timestamp", {}).get("S"),
        "type": "AI_SUMMARY",
        "description": "AI-generated summary added",
        "source": "AI Scribe",
        "metadata": {
            "summaryText": new_image.get("summary_text", {}).get("S", "")[:200] + "...",  # Truncate for timeline
            "modelId": new_image.get("model_id", {}).get("S")
        }
    }
    
    # Execute mutation
    try:
        appsync_client.execute_mutation(ADD_TIMELINE_EVENT_MUTATION, {"input": summary_event_input})
        metrics.add_metric(name="AISummaryPropagated", unit=MetricUnit.Count, value=1)
    except Exception as e:
        logger.error(f"Failed to propagate AI summary: {str(e)}")
        metrics.add_metric(name="PropagationError", unit=MetricUnit.Count, value=1)


@logger.inject_lambda_context
@tracer.capture_lambda_handler
@metrics.log_metrics(capture_cold_start_metric=True)
@event_source(data_class=DynamoDBStreamEvent)
def handler(event: DynamoDBStreamEvent, context: LambdaContext) -> Dict[str, Any]:
    """
    Lambda handler for real-time propagation.
    Processes DynamoDB Stream records and updates AppSync.
    """
    try:
        logger.info(f"Processing {len(event.records)} stream records")
        
        processed = 0
        errors = 0
        
        for record in event.records:
            try:
                # Get the event name (INSERT, MODIFY, REMOVE)
                event_name = record.event_name
                
                # Get the stream record
                stream_record = record.dynamodb
                
                # Process the record
                process_stream_record(stream_record, event_name)
                processed += 1
                
            except Exception as e:
                logger.error(f"Failed to process record: {str(e)}", exc_info=True)
                errors += 1
                # Continue processing other records
        
        logger.info(f"Stream processing complete. Processed: {processed}, Errors: {errors}")
        
        # Return success even if some records failed
        # This prevents the entire batch from being retried
        return {
            "statusCode": 200,
            "batchItemFailures": [],  # Could implement partial batch failure
            "body": json.dumps({
                "processed": processed,
                "errors": errors
            })
        }
        
    except Exception as e:
        logger.error(f"Critical error in stream handler: {str(e)}", exc_info=True)
        metrics.add_metric(name="StreamHandlerError", unit=MetricUnit.Count, value=1)
        raise