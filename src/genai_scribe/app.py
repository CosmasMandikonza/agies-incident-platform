"""
GenAI Scribe Lambda Function
Uses Amazon Bedrock to provide AI-powered incident analysis and summarization.
"""

import json
import uuid
from datetime import datetime
from typing import Dict, Any, List, Optional
import boto3
from aws_lambda_powertools import Logger, Tracer, Metrics
from aws_lambda_powertools.metrics import MetricUnit
from aws_lambda_powertools.utilities.typing import LambdaContext
from aws_lambda_powertools.utilities.data_classes import EventBridgeEvent, event_source

# Import shared modules
from shared.config import Config
from shared.models import AISummary, TimelineEvent
from shared.dynamodb_client import DynamoDBClient
from shared.event_publisher import EventPublisher
from shared.constants import (
    EVENT_SOURCE_INCIDENTS,
    EVENT_TYPE_AI_SUMMARY_GENERATED,
    EVENT_TYPE_TIMELINE_EVENT_ADDED
)
from shared.exceptions import AIServiceError, IncidentNotFoundError

# Initialize AWS Lambda Powertools
logger = Logger()
tracer = Tracer()
metrics = Metrics()

# Initialize configuration
config = Config()

# Initialize clients
dynamodb_client = DynamoDBClient(config.table_name)
event_publisher = EventPublisher(config.event_bus_name)
bedrock_runtime = boto3.client('bedrock-runtime')


class BedrockService:
    """Service for interacting with Amazon Bedrock."""
    
    def __init__(self, model_id: str, max_tokens: int, temperature: float):
        """Initialize Bedrock service."""
        self.model_id = model_id
        self.max_tokens = max_tokens
        self.temperature = temperature
        self.client = bedrock_runtime
    
    @tracer.capture_method
    def generate_summary(self, context: str, prompt_type: str) -> Dict[str, Any]:
        """Generate summary using Bedrock."""
        try:
            if config.mock_ai_responses:
                return self._mock_response(prompt_type)
            
            # Prepare the prompt based on type
            if prompt_type == "incident_summary":
                prompt = self._build_incident_summary_prompt(context)
            elif prompt_type == "post_mortem":
                prompt = self._build_post_mortem_prompt(context)
            else:
                prompt = self._build_timeline_summary_prompt(context)
            
            # Call Bedrock
            response = self.client.invoke_model(
                modelId=self.model_id,
                body=json.dumps({
                    "anthropic_version": "bedrock-2023-05-31",
                    "max_tokens": self.max_tokens,
                    "temperature": self.temperature,
                    "messages": [
                        {
                            "role": "user",
                            "content": prompt
                        }
                    ]
                })
            )
            
            # Parse response
            response_body = json.loads(response['body'].read())
            completion = response_body['content'][0]['text']
            
            # Extract token usage
            usage = response_body.get('usage', {})
            
            logger.info("Bedrock summary generated successfully", extra={
                "prompt_type": prompt_type,
                "prompt_tokens": usage.get('input_tokens', 0),
                "completion_tokens": usage.get('output_tokens', 0)
            })
            
            return {
                "summary": completion,
                "prompt_tokens": usage.get('input_tokens', 0),
                "completion_tokens": usage.get('output_tokens', 0)
            }
            
        except Exception as e:
            logger.error(f"Bedrock API error: {str(e)}", exc_info=True)
            raise AIServiceError(f"Failed to generate summary: {str(e)}")
    
    def _build_incident_summary_prompt(self, context: str) -> str:
        """Build prompt for incident summary."""
        return f"""You are an AI assistant helping with incident management. Please analyze the following incident information and timeline events, then provide a concise summary.

Incident Context:
{context}

Please provide:
1. A brief summary of what happened (2-3 sentences)
2. Key findings or observations
3. Current status and any immediate actions needed

Keep your response concise and actionable, focusing on the most important information for incident responders."""
    
    def _build_timeline_summary_prompt(self, context: str) -> str:
        """Build prompt for timeline summary."""
        return f"""You are an AI assistant helping with incident management. Please analyze the recent timeline events and comments for this incident.

Recent Activity:
{context}

Please provide a brief summary of:
1. What has happened in the last period
2. Key decisions or actions taken
3. Any patterns or concerns observed

Keep your response to 3-4 sentences maximum, highlighting only the most relevant information."""
    
    def _build_post_mortem_prompt(self, context: str) -> str:
        """Build prompt for post-mortem generation."""
        return f"""You are an AI assistant helping create a post-mortem report. Please analyze the complete incident timeline and generate a structured post-mortem.

Incident Information:
{context}

Please create a post-mortem report with these sections:

## Executive Summary
(2-3 sentences summarizing the incident and impact)

## Timeline
(Key events in chronological order)

## Root Cause Analysis
(What caused the incident)

## Impact
(Who/what was affected and how)

## What Went Well
(Positive aspects of the incident response)

## What Could Be Improved
(Areas for improvement)

## Action Items
(Specific follow-up tasks with priorities)

Be specific and actionable in your recommendations."""
    
    def _mock_response(self, prompt_type: str) -> Dict[str, Any]:
        """Return mock response for testing."""
        responses = {
            "incident_summary": {
                "summary": "Mock Summary: Database connection pool exhaustion caused service degradation. Team identified root cause as misconfigured connection limits. Immediate mitigation applied by increasing pool size.",
                "prompt_tokens": 150,
                "completion_tokens": 50
            },
            "post_mortem": {
                "summary": """## Executive Summary
Mock post-mortem for testing. Service experienced degradation due to database issues.

## Timeline
- 10:00 - Alert triggered
- 10:05 - Team acknowledged
- 10:30 - Root cause identified
- 10:45 - Fix deployed

## Root Cause Analysis
Database connection pool exhaustion.

## Action Items
1. Increase connection pool size
2. Add better monitoring""",
                "prompt_tokens": 500,
                "completion_tokens": 200
            },
            "timeline_summary": {
                "summary": "Recent activity shows team investigating database performance issues. Connection pool increased from 20 to 50. Monitoring enhanced.",
                "prompt_tokens": 100,
                "completion_tokens": 30
            }
        }
        
        return responses.get(prompt_type, responses["incident_summary"])


# Initialize Bedrock service
bedrock_service = BedrockService(
    model_id=config.bedrock_model_id,
    max_tokens=config.bedrock_max_tokens,
    temperature=config.bedrock_temperature
)


@tracer.capture_method
def process_timeline_event(detail: Dict[str, Any]) -> None:
    """Process new timeline event and generate summary if needed."""
    incident_id = detail["incidentId"]
    
    logger.info(f"Processing timeline event for incident {incident_id}")
    
    try:
        # Get recent timeline events
        incident_data = dynamodb_client.get_incident(incident_id)
        timeline_events = incident_data.get("timeline", [])
        recent_comments = incident_data.get("comments", [])
        
        # Check if we have enough new activity to warrant a summary
        total_events = len(timeline_events) + len(recent_comments)
        existing_summaries = incident_data.get("summaries", [])
        
        # Generate summary every 10 events or if no summary exists
        if total_events > 0 and (total_events % 10 == 0 or len(existing_summaries) == 0):
            generate_timeline_summary(incident_id, timeline_events, recent_comments)
            
    except IncidentNotFoundError:
        logger.warning(f"Incident {incident_id} not found")
    except Exception as e:
        logger.error(f"Failed to process timeline event: {str(e)}", exc_info=True)
        raise


@tracer.capture_method
def process_incident_resolved(detail: Dict[str, Any]) -> None:
    """Process incident resolution and generate post-mortem."""
    incident_id = detail["incidentId"]
    
    logger.info(f"Processing incident resolution for {incident_id}")
    
    try:
        # Get complete incident data
        incident_data = dynamodb_client.get_incident(incident_id)
        
        # Generate post-mortem
        generate_post_mortem(incident_id, incident_data)
        
    except IncidentNotFoundError:
        logger.warning(f"Incident {incident_id} not found")
    except Exception as e:
        logger.error(f"Failed to process incident resolution: {str(e)}", exc_info=True)
        raise


@tracer.capture_method
def generate_timeline_summary(incident_id: str, timeline_events: List[Dict], 
                            comments: List[Dict]) -> None:
    """Generate AI summary of recent timeline activity."""
    # Prepare context for AI
    context_parts = []
    
    # Add recent timeline events
    recent_events = sorted(timeline_events, key=lambda x: x['timestamp'], reverse=True)[:5]
    for event in recent_events:
        context_parts.append(f"[{event['timestamp']}] {event['type']}: {event['description']}")
    
    # Add recent comments
    recent_comments = sorted(comments, key=lambda x: x['timestamp'], reverse=True)[:5]
    for comment in recent_comments:
        context_parts.append(f"[{comment['timestamp']}] Comment by {comment['author_name']}: {comment['text']}")
    
    context = "\n".join(context_parts)
    
    # Generate summary
    result = bedrock_service.generate_summary(context, "timeline_summary")
    
    # Save summary to DynamoDB
    summary = AISummary(
        incident_id=incident_id,
        summary_id=str(uuid.uuid4()),
        summary_text=result["summary"],
        model_id=config.bedrock_model_id,
        prompt_tokens=result.get("prompt_tokens"),
        completion_tokens=result.get("completion_tokens")
    )
    
    dynamodb_client.put_item(summary.to_dynamodb_item())
    
    # Publish event
    event_publisher.publish_incident_event(
        incident_id=incident_id,
        detail_type=EVENT_TYPE_AI_SUMMARY_GENERATED,
        additional_detail={
            "summaryType": "timeline",
            "summaryId": summary.summary_id
        }
    )
    
    # Emit metrics
    metrics.add_metric(name="TimelineSummaryGenerated", unit=MetricUnit.Count, value=1)
    metrics.add_metric(name="TokensUsed", unit=MetricUnit.Count, 
                      value=result.get("prompt_tokens", 0) + result.get("completion_tokens", 0))


@tracer.capture_method
def generate_post_mortem(incident_id: str, incident_data: Dict[str, Any]) -> None:
    """Generate AI-powered post-mortem report."""
    # Prepare comprehensive context
    context_parts = []
    
    # Add incident metadata
    metadata = incident_data["metadata"]
    context_parts.append(f"Incident: {metadata['title']}")
    context_parts.append(f"Severity: {metadata['severity']}")
    context_parts.append(f"Created: {metadata['created_at']}")
    context_parts.append(f"Resolved: {metadata.get('resolved_at', 'Not yet resolved')}")
    context_parts.append(f"Description: {metadata.get('description', 'No description provided')}")
    context_parts.append("\nTimeline:")
    
    # Add all timeline events
    all_events = sorted(incident_data.get("timeline", []), key=lambda x: x['timestamp'])
    for event in all_events:
        context_parts.append(f"- [{event['timestamp']}] {event['type']}: {event['description']}")
    
    # Add participant information
    if incident_data.get("participants"):
        context_parts.append("\nParticipants:")
        for participant in incident_data["participants"]:
            context_parts.append(f"- {participant['name']} ({participant['role']})")
    
    context = "\n".join(context_parts)
    
    # Generate post-mortem
    result = bedrock_service.generate_summary(context, "post_mortem")
    
    # Save post-mortem as special timeline event
    post_mortem_event = TimelineEvent(
        incident_id=incident_id,
        event_id=str(uuid.uuid4()),
        type="POST_MORTEM_GENERATED",
        description="AI-generated post-mortem report",
        source="AI Scribe",
        metadata={
            "post_mortem_content": result["summary"],
            "model_id": config.bedrock_model_id,
            "tokens_used": result.get("prompt_tokens", 0) + result.get("completion_tokens", 0)
        }
    )
    
    dynamodb_client.put_item(post_mortem_event.to_dynamodb_item())
    
    # Also save as AI summary for easy retrieval
    summary = AISummary(
        incident_id=incident_id,
        summary_id=str(uuid.uuid4()),
        summary_text=result["summary"],
        model_id=config.bedrock_model_id,
        prompt_tokens=result.get("prompt_tokens"),
        completion_tokens=result.get("completion_tokens")
    )
    
    dynamodb_client.put_item(summary.to_dynamodb_item())
    
    # Publish events
    event_publisher.publish_incident_event(
        incident_id=incident_id,
        detail_type=EVENT_TYPE_TIMELINE_EVENT_ADDED,
        additional_detail={
            "eventType": "POST_MORTEM_GENERATED",
            "eventId": post_mortem_event.event_id
        }
    )
    
    event_publisher.publish_incident_event(
        incident_id=incident_id,
        detail_type=EVENT_TYPE_AI_SUMMARY_GENERATED,
        additional_detail={
            "summaryType": "post_mortem",
            "summaryId": summary.summary_id
        }
    )
    
    # Emit metrics
    metrics.add_metric(name="PostMortemGenerated", unit=MetricUnit.Count, value=1)
    metrics.add_metric(name="TokensUsed", unit=MetricUnit.Count, 
                      value=result.get("prompt_tokens", 0) + result.get("completion_tokens", 0))


@logger.inject_lambda_context
@tracer.capture_lambda_handler
@metrics.log_metrics(capture_cold_start_metric=True)
@event_source(data_class=EventBridgeEvent)
def handler(event: EventBridgeEvent, context: LambdaContext) -> Dict[str, Any]:
    """
    Lambda handler for GenAI Scribe.
    Processes EventBridge events for AI-powered analysis.
    """
    try:
        logger.info("GenAI Scribe invoked", extra={
            "source": event.source,
            "detail_type": event.detail_type
        })
        
        # Route based on event type
        if event.detail_type in ["Timeline Event Added", "Comment Added"]:
            process_timeline_event(event.detail)
        elif event.detail_type == "Incident Resolved":
            process_incident_resolved(event.detail)
        else:
            logger.warning(f"Unsupported event type: {event.detail_type}")
        
        return {
            "statusCode": 200,
            "body": json.dumps({
                "message": "Event processed successfully",
                "eventType": event.detail_type
            })
        }
        
    except Exception as e:
        logger.error(f"Error processing event: {str(e)}", exc_info=True)
        metrics.add_metric(name="ProcessingError", unit=MetricUnit.Count, value=1)
        raise