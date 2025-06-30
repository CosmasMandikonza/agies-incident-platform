"""EventBridge event publisher for Aegis platform."""

import json
from typing import Dict, Any, List, Optional
from datetime import datetime
import boto3
from botocore.exceptions import ClientError
from aws_lambda_powertools import Logger, Tracer
from shared.exceptions import ExternalServiceError

logger = Logger()
tracer = Tracer()


class EventPublisher:
    """Publisher for EventBridge events."""
    
    def __init__(self, event_bus_name: str, region: Optional[str] = None):
        """Initialize EventBridge client."""
        self.event_bus_name = event_bus_name
        self.region = region or "us-east-1"
        self.client = boto3.client("events", region_name=self.region)
        
        logger.info(f"Initialized EventBridge publisher for bus: {event_bus_name}")
    
    @tracer.capture_method
    def publish_event(self, source: str, detail_type: str, detail: Dict[str, Any]) -> str:
        """Publish a single event to EventBridge."""
        try:
            # Ensure detail is JSON serializable
            detail_json = json.dumps(detail, default=str)
            
            response = self.client.put_events(
                Entries=[
                    {
                        "Source": source,
                        "DetailType": detail_type,
                        "Detail": detail_json,
                        "EventBusName": self.event_bus_name,
                        "Time": datetime.utcnow()
                    }
                ]
            )
            
            # Check for failures
            if response["FailedEntryCount"] > 0:
                failed_entry = response["Entries"][0]
                error_msg = f"Failed to publish event: {failed_entry.get('ErrorMessage', 'Unknown error')}"
                logger.error(error_msg, extra={
                    "source": source,
                    "detail_type": detail_type,
                    "error_code": failed_entry.get("ErrorCode")
                })
                raise ExternalServiceError(error_msg)
            
            event_id = response["Entries"][0]["EventId"]
            logger.info("Event published successfully", extra={
                "event_id": event_id,
                "source": source,
                "detail_type": detail_type
            })
            
            return event_id
            
        except ClientError as e:
            error_msg = f"Failed to publish event to EventBridge: {str(e)}"
            logger.error(error_msg, extra={"error": str(e)})
            raise ExternalServiceError(error_msg)
    
    @tracer.capture_method
    def publish_batch_events(self, events: List[Dict[str, Any]]) -> List[str]:
        """Publish multiple events to EventBridge."""
        if not events:
            return []
        
        # EventBridge has a limit of 10 events per PutEvents call
        batch_size = 10
        all_event_ids = []
        
        for i in range(0, len(events), batch_size):
            batch = events[i:i + batch_size]
            
            try:
                entries = []
                for event in batch:
                    entries.append({
                        "Source": event["source"],
                        "DetailType": event["detail_type"],
                        "Detail": json.dumps(event["detail"], default=str),
                        "EventBusName": self.event_bus_name,
                        "Time": datetime.utcnow()
                    })
                
                response = self.client.put_events(Entries=entries)
                
                # Check for failures
                if response["FailedEntryCount"] > 0:
                    failed_entries = [
                        entry for entry in response["Entries"] 
                        if "ErrorCode" in entry
                    ]
                    logger.error(f"Failed to publish {len(failed_entries)} events", extra={
                        "failed_entries": failed_entries
                    })
                
                # Collect successful event IDs
                event_ids = [
                    entry["EventId"] for entry in response["Entries"] 
                    if "EventId" in entry
                ]
                all_event_ids.extend(event_ids)
                
                logger.info(f"Published batch of {len(event_ids)} events")
                
            except ClientError as e:
                logger.error(f"Failed to publish batch events: {str(e)}", extra={"error": str(e)})
                # Continue with next batch even if this one fails
                continue
        
        return all_event_ids
    
    def publish_incident_event(self, incident_id: str, detail_type: str, 
                              additional_detail: Optional[Dict[str, Any]] = None) -> str:
        """Publish an incident-related event."""
        detail = {
            "incidentId": incident_id,
            "timestamp": datetime.utcnow().isoformat()
        }
        
        if additional_detail:
            detail.update(additional_detail)
        
        return self.publish_event(
            source="aegis.incidents",
            detail_type=detail_type,
            detail=detail
        )
    
    def publish_workflow_event(self, incident_id: str, workflow_event: str,
                              metadata: Optional[Dict[str, Any]] = None) -> str:
        """Publish a workflow-related event."""
        detail = {
            "incidentId": incident_id,
            "workflowEvent": workflow_event,
            "timestamp": datetime.utcnow().isoformat()
        }
        
        if metadata:
            detail["metadata"] = metadata
        
        return self.publish_event(
            source="aegis.workflow",
            detail_type=f"Workflow {workflow_event}",
            detail=detail
        )
    
    def publish_notification_event(self, incident_id: str, notification_type: str,
                                  status: str, metadata: Optional[Dict[str, Any]] = None) -> str:
        """Publish a notification-related event."""
        detail = {
            "incidentId": incident_id,
            "notificationType": notification_type,
            "status": status,
            "timestamp": datetime.utcnow().isoformat()
        }
        
        if metadata:
            detail["metadata"] = metadata
        
        return self.publish_event(
            source="aegis.notifications",
            detail_type=f"Notification {status}",
            detail=detail
        )