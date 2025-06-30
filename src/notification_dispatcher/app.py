"""
Notification Dispatcher Lambda Function
Processes notification requests from SQS and sends to external services.
"""

import json
import os
from typing import Dict, Any, List, Optional
from datetime import datetime
import boto3
import httpx
from aws_lambda_powertools import Logger, Tracer, Metrics
from aws_lambda_powertools.metrics import MetricUnit
from aws_lambda_powertools.utilities.idempotency import (
    DynamoDBPersistenceLayer, idempotent, IdempotencyConfig
)
from aws_lambda_powertools.utilities.typing import LambdaContext
from aws_lambda_powertools.utilities.data_classes import SQSEvent, event_source
from aws_lambda_powertools.utilities.batch import BatchProcessor, EventType, batch_processor
from botocore.exceptions import ClientError

# Import shared modules
from shared.config import Config
from shared.models import NotificationRequest, NotificationType
from shared.event_publisher import EventPublisher
from shared.constants import EVENT_SOURCE_NOTIFICATIONS
from shared.exceptions import ExternalServiceError, ValidationError
from shared.utils import get_secret

# Initialize AWS Lambda Powertools
logger = Logger()
tracer = Tracer()
metrics = Metrics()

# Initialize configuration
config = Config()

# Initialize clients
event_publisher = EventPublisher(config.event_bus_name)
secrets_client = boto3.client('secretsmanager')

# Configure idempotency
persistence_layer = DynamoDBPersistenceLayer(
    table_name=config.idempotency_table_name
)
idempotency_config = IdempotencyConfig(
    expires_after_seconds=3600,  # 1 hour
)

# Initialize batch processor
processor = BatchProcessor(event_type=EventType.SQS)


class NotificationService:
    """Service for sending notifications to external systems."""
    
    def __init__(self):
        """Initialize notification service."""
        self.secrets_cache = {}
        self.http_client = httpx.Client(timeout=30.0)
    
    @tracer.capture_method
    def send_notification(self, notification: NotificationRequest) -> Dict[str, Any]:
        """Send notification based on type."""
        try:
            if config.mock_external_services:
                logger.info("Mocking external notification service")
                return self._mock_send(notification)
            
            # Route to appropriate handler
            if notification.type == NotificationType.SLACK:
                return self._send_slack(notification)
            elif notification.type == NotificationType.EMAIL:
                return self._send_email(notification)
            elif notification.type == NotificationType.PAGE:
                return self._send_page(notification)
            elif notification.type == NotificationType.SMS:
                return self._send_sms(notification)
            else:
                raise ValueError(f"Unsupported notification type: {notification.type}")
                
        except Exception as e:
            logger.error(f"Failed to send notification: {str(e)}", extra={
                "notification_id": notification.notification_id,
                "type": notification.type
            })
            raise
    
    def _mock_send(self, notification: NotificationRequest) -> Dict[str, Any]:
        """Mock sending for local testing."""
        logger.info(f"Mock sending {notification.type} notification", extra={
            "target": notification.target,
            "message": notification.message[:100]
        })
        return {
            "status": "sent",
            "message_id": f"mock-{notification.notification_id}",
            "timestamp": datetime.utcnow().isoformat()
        }
    
    @tracer.capture_method
    def _send_slack(self, notification: NotificationRequest) -> Dict[str, Any]:
        """Send Slack notification."""
        # Get Slack webhook URL from secrets
        secrets = self._get_secrets()
        webhook_url = secrets.get("slack_webhook")
        
        if not webhook_url:
            raise ExternalServiceError("Slack webhook URL not configured")
        
        # Prepare Slack message
        slack_message = {
            "channel": notification.target,
            "username": "Aegis Incident Bot",
            "icon_emoji": ":warning:",
            "attachments": [{
                "color": self._get_slack_color(notification.priority),
                "title": f"Incident Alert - {notification.metadata.get('severity', 'Unknown')}",
                "text": notification.message,
                "fields": [
                    {
                        "title": "Incident ID",
                        "value": notification.incident_id,
                        "short": True
                    },
                    {
                        "title": "Priority",
                        "value": notification.priority.upper(),
                        "short": True
                    }
                ],
                "footer": "Aegis Incident Management",
                "ts": int(datetime.utcnow().timestamp())
            }]
        }
        
        # Send to Slack
        response = self.http_client.post(webhook_url, json=slack_message)
        
        if response.status_code != 200:
            raise ExternalServiceError(f"Slack API error: {response.status_code} - {response.text}")
        
        logger.info("Slack notification sent successfully", extra={
            "channel": notification.target,
            "incident_id": notification.incident_id
        })
        
        return {
            "status": "sent",
            "channel": notification.target,
            "timestamp": datetime.utcnow().isoformat()
        }
    
    @tracer.capture_method
    def _send_email(self, notification: NotificationRequest) -> Dict[str, Any]:
        """Send email notification via SES."""
        ses_client = boto3.client('ses')
        
        try:
            response = ses_client.send_email(
                Source='aegis-noreply@example.com',  # Configure this
                Destination={'ToAddresses': [notification.target]},
                Message={
                    'Subject': {
                        'Data': f"[Aegis] Incident Alert - {notification.metadata.get('severity', 'Unknown')}"
                    },
                    'Body': {
                        'Text': {'Data': notification.message},
                        'Html': {'Data': self._format_email_html(notification)}
                    }
                }
            )
            
            logger.info("Email notification sent successfully", extra={
                "recipient": notification.target,
                "message_id": response['MessageId']
            })
            
            return {
                "status": "sent",
                "message_id": response['MessageId'],
                "timestamp": datetime.utcnow().isoformat()
            }
            
        except ClientError as e:
            raise ExternalServiceError(f"Failed to send email: {str(e)}")
    
    @tracer.capture_method
    def _send_page(self, notification: NotificationRequest) -> Dict[str, Any]:
        """Send page via PagerDuty."""
        # Get PagerDuty API key from secrets
        secrets = self._get_secrets()
        api_key = secrets.get("pagerduty_api_key")
        
        if not api_key:
            raise ExternalServiceError("PagerDuty API key not configured")
        
        # Prepare PagerDuty event
        pagerduty_event = {
            "routing_key": notification.target,
            "event_action": "trigger",
            "payload": {
                "summary": notification.message,
                "severity": self._map_to_pagerduty_severity(notification.priority),
                "source": "aegis-incident-management",
                "custom_details": {
                    "incident_id": notification.incident_id,
                    "priority": notification.priority,
                    **notification.metadata
                }
            }
        }
        
        # Send to PagerDuty
        response = self.http_client.post(
            "https://events.pagerduty.com/v2/enqueue",
            json=pagerduty_event,
            headers={
                "Content-Type": "application/json",
                "Accept": "application/vnd.pagerduty+json;version=2"
            }
        )
        
        if response.status_code != 202:
            raise ExternalServiceError(f"PagerDuty API error: {response.status_code} - {response.text}")
        
        result = response.json()
        logger.info("Page sent successfully via PagerDuty", extra={
            "dedup_key": result.get("dedup_key"),
            "incident_id": notification.incident_id
        })
        
        return {
            "status": "sent",
            "dedup_key": result.get("dedup_key"),
            "timestamp": datetime.utcnow().isoformat()
        }
    
    @tracer.capture_method
    def _send_sms(self, notification: NotificationRequest) -> Dict[str, Any]:
        """Send SMS via SNS."""
        sns_client = boto3.client('sns')
        
        try:
            response = sns_client.publish(
                PhoneNumber=notification.target,
                Message=f"[Aegis Alert] {notification.message[:140]}",  # SMS length limit
                MessageAttributes={
                    'AWS.SNS.SMS.SMSType': {
                        'DataType': 'String',
                        'StringValue': 'Transactional'
                    }
                }
            )
            
            logger.info("SMS notification sent successfully", extra={
                "phone_number": notification.target[-4:],  # Log last 4 digits only
                "message_id": response['MessageId']
            })
            
            return {
                "status": "sent",
                "message_id": response['MessageId'],
                "timestamp": datetime.utcnow().isoformat()
            }
            
        except ClientError as e:
            raise ExternalServiceError(f"Failed to send SMS: {str(e)}")
    
    def _get_secrets(self) -> Dict[str, Any]:
        """Get notification secrets from cache or Secrets Manager."""
        if "notification_secrets" in self.secrets_cache:
            return self.secrets_cache["notification_secrets"]
        
        secrets = get_secret(f"{config.environment}-notification-secrets")
        self.secrets_cache["notification_secrets"] = secrets
        return secrets
    
    def _get_slack_color(self, priority: str) -> str:
        """Map priority to Slack attachment color."""
        colors = {
            "critical": "#FF0000",  # Red
            "high": "#FF9900",      # Orange
            "normal": "#FFCC00",    # Yellow
            "low": "#00CC00"        # Green
        }
        return colors.get(priority, "#808080")  # Default gray
    
    def _map_to_pagerduty_severity(self, priority: str) -> str:
        """Map internal priority to PagerDuty severity."""
        mapping = {
            "critical": "critical",
            "high": "error",
            "normal": "warning",
            "low": "info"
        }
        return mapping.get(priority, "warning")
    
    def _format_email_html(self, notification: NotificationRequest) -> str:
        """Format HTML email body."""
        return f"""
        <html>
        <body style="font-family: Arial, sans-serif;">
            <h2 style="color: #ff6b6b;">Aegis Incident Alert</h2>
            <p><strong>Incident ID:</strong> {notification.incident_id}</p>
            <p><strong>Severity:</strong> {notification.metadata.get('severity', 'Unknown')}</p>
            <p><strong>Priority:</strong> {notification.priority.upper()}</p>
            <hr>
            <p>{notification.message}</p>
            <hr>
            <p style="color: #666; font-size: 12px;">
                This is an automated notification from Aegis Incident Management System.
            </p>
        </body>
        </html>
        """


# Initialize notification service
notification_service = NotificationService()


@tracer.capture_method
@idempotent(
    persistence_store=persistence_layer,
    config=idempotency_config,
    data_keyword_argument="record"
)
def process_notification(record: Dict[str, Any]) -> Dict[str, Any]:
    """Process a single notification request."""
    try:
        # Parse message body
        message_body = json.loads(record["body"])
        
        # Create notification request model
        notification = NotificationRequest(
            notification_id=record["messageId"],
            incident_id=message_body["incidentId"],
            type=NotificationType(message_body["type"]),
            target=message_body["target"],
            message=message_body["message"],
            priority=message_body.get("priority", "normal"),
            metadata=message_body.get("metadata", {})
        )
        
        # Send notification
        result = notification_service.send_notification(notification)
        
        # Publish success event
        event_publisher.publish_notification_event(
            incident_id=notification.incident_id,
            notification_type=notification.type,
            status="sent",
            metadata={
                "notification_id": notification.notification_id,
                "target": notification.target,
                **result
            }
        )
        
        # Emit metrics
        metrics.add_metric(name="NotificationSent", unit=MetricUnit.Count, value=1)
        metrics.add_metadata(key="type", value=notification.type)
        metrics.add_metadata(key="priority", value=notification.priority)
        
        return result
        
    except Exception as e:
        logger.error(f"Failed to process notification: {str(e)}", exc_info=True)
        
        # Publish failure event
        if 'notification' in locals():
            event_publisher.publish_notification_event(
                incident_id=notification.incident_id,
                notification_type=notification.type,
                status="failed",
                metadata={
                    "notification_id": notification.notification_id,
                    "error": str(e)
                }
            )
        
        # Emit failure metric
        metrics.add_metric(name="NotificationFailed", unit=MetricUnit.Count, value=1)
        
        raise


def record_handler(record: Dict[str, Any]) -> Dict[str, Any]:
    """Handler for batch processor."""
    return process_notification(record)


@logger.inject_lambda_context
@tracer.capture_lambda_handler
@metrics.log_metrics(capture_cold_start_metric=True)
@event_source(data_class=SQSEvent)
def handler(event: SQSEvent, context: LambdaContext) -> Dict[str, Any]:
    """
    Lambda handler for notification dispatcher.
    Processes notification requests from SQS queue.
    """
    return batch_processor(
        event=event,
        record_handler=record_handler,
        processor=processor,
        context=context
    )