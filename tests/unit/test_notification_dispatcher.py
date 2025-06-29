"""
Unit tests for Notification Dispatcher Lambda function
"""

import json
import os
from unittest.mock import Mock, patch, MagicMock
import pytest
from moto import mock_sqs, mock_secretsmanager, mock_ses
import boto3
import httpx

# Set environment variables
os.environ['TABLE_NAME'] = 'test-incidents'
os.environ['IDEMPOTENCY_TABLE_NAME'] = 'test-idempotency'
os.environ['MOCK_EXTERNAL_SERVICES'] = 'false'
os.environ['AWS_DEFAULT_REGION'] = 'us-east-1'

from src.notification_dispatcher.app import (
    handler,
    process_notification,
    NotificationService,
    notification_service
)
from shared.models import NotificationRequest, NotificationType


@pytest.fixture
def sqs_event():
    """Sample SQS event with notification requests."""
    return {
        "Records": [
            {
                "messageId": "msg-001",
                "receiptHandle": "receipt-001",
                "body": json.dumps({
                    "incidentId": "INC-001",
                    "type": "SLACK",
                    "target": "#incidents",
                    "message": "Test incident notification",
                    "priority": "high",
                    "metadata": {"severity": "P1"}
                }),
                "attributes": {
                    "ApproximateReceiveCount": "1"
                }
            }
        ]
    }


@pytest.fixture
def lambda_context():
    """Mock Lambda context."""
    context = Mock()
    context.request_id = "test-request-id"
    context.function_name = "test-notification-dispatcher"
    return context


@pytest.fixture
def mock_secrets():
    """Mock secrets for notification services."""
    with mock_secretsmanager():
        client = boto3.client('secretsmanager', region_name='us-east-1')
        client.create_secret(
            Name='test-notification-secrets',
            SecretString=json.dumps({
                "slack_webhook": "https://hooks.slack.com/test",
                "pagerduty_api_key": "test-pd-key"
            })
        )
        yield client


class TestNotificationDispatcher:
    """Test cases for notification dispatcher."""
    
    @patch('src.notification_dispatcher.app.persistence_layer')
    @patch('src.notification_dispatcher.app.event_publisher')
    def test_handler_success(self, mock_publisher, mock_persistence, sqs_event, lambda_context):
        """Test successful notification processing."""
        # Mock idempotency check
        mock_persistence.get_record.return_value = None
        mock_persistence.put_record.return_value = None
        
        # Mock notification service
        with patch.object(notification_service, 'send_notification') as mock_send:
            mock_send.return_value = {
                "status": "sent",
                "channel": "#incidents",
                "timestamp": "2025-01-15T10:00:00Z"
            }
            
            result = handler(sqs_event, lambda_context)
            
            assert result['batchItemFailures'] == []
            mock_send.assert_called_once()
            mock_publisher.publish_notification_event.assert_called_once()
    
    @patch('src.notification_dispatcher.app.persistence_layer')
    def test_handler_idempotent(self, mock_persistence, sqs_event, lambda_context):
        """Test idempotent notification processing."""
        # Mock that we've already processed this message
        mock_persistence.get_record.return_value = {
            "id": "msg-001",
            "status": "COMPLETED",
            "result": {"status": "sent"}
        }
        
        result = handler(sqs_event, lambda_context)
        
        assert result['batchItemFailures'] == []
        # Notification service should not be called due to idempotency
    
    def test_process_notification_slack(self, mock_secrets):
        """Test Slack notification processing."""
        record = {
            "messageId": "msg-001",
            "body": json.dumps({
                "incidentId": "INC-001",
                "type": "SLACK",
                "target": "#incidents",
                "message": "Test notification",
                "priority": "high",
                "metadata": {"severity": "P1"}
            })
        }
        
        with patch('httpx.Client.post') as mock_post, \
             patch('src.notification_dispatcher.app.event_publisher') as mock_publisher:
            
            mock_response = Mock()
            mock_response.status_code = 200
            mock_response.text = "ok"
            mock_post.return_value = mock_response
            
            result = process_notification(record)
            
            assert result["status"] == "sent"
            assert result["channel"] == "#incidents"
            
            # Verify Slack webhook was called
            mock_post.assert_called_once()
            call_args = mock_post.call_args
            assert "hooks.slack.com" in call_args[0][0]
            
            # Verify event was published
            mock_publisher.publish_notification_event.assert_called_once()
    
    @mock_ses
    def test_process_notification_email(self):
        """Test email notification processing."""
        # Setup SES
        ses_client = boto3.client('ses', region_name='us-east-1')
        ses_client.verify_email_identity(EmailAddress='aegis-noreply@example.com')
        ses_client.verify_email_identity(EmailAddress='test@example.com')
        
        record = {
            "messageId": "msg-002",
            "body": json.dumps({
                "incidentId": "INC-002",
                "type": "EMAIL",
                "target": "test@example.com",
                "message": "Email notification test",
                "priority": "normal",
                "metadata": {"severity": "P2"}
            })
        }
        
        with patch('src.notification_dispatcher.app.event_publisher') as mock_publisher:
            result = process_notification(record)
            
            assert result["status"] == "sent"
            assert "message_id" in result
    
    def test_process_notification_page(self, mock_secrets):
        """Test PagerDuty notification processing."""
        record = {
            "messageId": "msg-003",
            "body": json.dumps({
                "incidentId": "INC-003",
                "type": "PAGE",
                "target": "service-key-123",
                "message": "Critical incident requiring immediate attention",
                "priority": "critical",
                "metadata": {"severity": "P0"}
            })
        }
        
        with patch('httpx.Client.post') as mock_post, \
             patch('src.notification_dispatcher.app.event_publisher') as mock_publisher:
            
            mock_response = Mock()
            mock_response.status_code = 202
            mock_response.json.return_value = {"dedup_key": "dedup-123"}
            mock_post.return_value = mock_response
            
            result = process_notification(record)
            
            assert result["status"] == "sent"
            assert result["dedup_key"] == "dedup-123"
            
            # Verify PagerDuty API was called
            mock_post.assert_called_once()
            call_args = mock_post.call_args
            assert "events.pagerduty.com" in call_args[0][0]
    
    def test_process_notification_failure(self, mock_secrets):
        """Test notification failure handling."""
        record = {
            "messageId": "msg-004",
            "body": json.dumps({
                "incidentId": "INC-004",
                "type": "SLACK",
                "target": "#incidents",
                "message": "Test notification",
                "priority": "normal",
                "metadata": {}
            })
        }
        
        with patch('httpx.Client.post') as mock_post, \
             patch('src.notification_dispatcher.app.event_publisher') as mock_publisher:
            
            # Simulate API failure
            mock_post.side_effect = httpx.HTTPError("Connection failed")
            
            with pytest.raises(httpx.HTTPError):
                process_notification(record)
            
            # Verify failure event was published
            mock_publisher.publish_notification_event.assert_called_once()
            call_args = mock_publisher.publish_notification_event.call_args
            assert call_args[1]['status'] == 'failed'


class TestNotificationService:
    """Test cases for NotificationService class."""
    
    def test_mock_mode(self):
        """Test mock mode for local development."""
        os.environ['MOCK_EXTERNAL_SERVICES'] = 'true'
        service = NotificationService()
        
        notification = NotificationRequest(
            notification_id="test-001",
            incident_id="INC-001",
            type=NotificationType.SLACK,
            target="#test",
            message="Test message",
            priority="normal"
        )
        
        result = service.send_notification(notification)
        
        assert result["status"] == "sent"
        assert result["message_id"].startswith("mock-")
        
        os.environ['MOCK_EXTERNAL_SERVICES'] = 'false'
    
    def test_slack_color_mapping(self):
        """Test Slack color mapping for priorities."""
        service = NotificationService()
        
        assert service._get_slack_color("critical") == "#FF0000"
        assert service._get_slack_color("high") == "#FF9900"
        assert service._get_slack_color("normal") == "#FFCC00"
        assert service._get_slack_color("low") == "#00CC00"
        assert service._get_slack_color("unknown") == "#808080"
    
    def test_pagerduty_severity_mapping(self):
        """Test PagerDuty severity mapping."""
        service = NotificationService()
        
        assert service._map_to_pagerduty_severity("critical") == "critical"
        assert service._map_to_pagerduty_severity("high") == "error"
        assert service._map_to_pagerduty_severity("normal") == "warning"
        assert service._map_to_pagerduty_severity("low") == "info"
        assert service._map_to_pagerduty_severity("unknown") == "warning"
    
    def test_email_html_formatting(self):
        """Test email HTML formatting."""
        service = NotificationService()
        
        notification = NotificationRequest(
            notification_id="test-001",
            incident_id="INC-001",
            type=NotificationType.EMAIL,
            target="test@example.com",
            message="Test incident message",
            priority="high",
            metadata={"severity": "P1"}
        )
        
        html = service._format_email_html(notification)
        
        assert "INC-001" in html
        assert "P1" in html
        assert "HIGH" in html
        assert "Test incident message" in html
    
    def test_sms_message_truncation(self):
        """Test SMS message truncation to 140 characters."""
        with patch('boto3.client') as mock_boto:
            mock_sns = Mock()
            mock_boto.return_value = mock_sns
            mock_sns.publish.return_value = {"MessageId": "msg-123"}
            
            service = NotificationService()
            
            notification = NotificationRequest(
                notification_id="test-001",
                incident_id="INC-001",
                type=NotificationType.SMS,
                target="+1234567890",
                message="x" * 200,  # Long message
                priority="high"
            )
            
            result = service._send_sms(notification)
            
            # Verify message was truncated
            call_args = mock_sns.publish.call_args
            message = call_args[1]['Message']
            assert len(message) <= 160  # SMS limit with prefix
            assert "[Aegis Alert]" in message
    
    def test_secrets_caching(self, mock_secrets):
        """Test secrets are cached after first retrieval."""
        service = NotificationService()
        
        # First call should fetch from Secrets Manager
        secrets1 = service._get_secrets()
        assert "slack_webhook" in secrets1
        
        # Second call should use cache
        with patch('boto3.client') as mock_boto:
            secrets2 = service._get_secrets()
            assert secrets1 == secrets2
            # Boto3 client should not be called due to caching
            mock_boto.assert_not_called()


class TestNotificationValidation:
    """Test cases for notification validation."""
    
    def test_valid_notification_types(self):
        """Test all valid notification types."""
        for ntype in ['SLACK', 'EMAIL', 'PAGE', 'SMS']:
            record = {
                "messageId": f"msg-{ntype}",
                "body": json.dumps({
                    "incidentId": "INC-001",
                    "type": ntype,
                    "target": "test-target",
                    "message": "Test message",
                    "priority": "normal"
                })
            }
            
            with patch.object(notification_service, 'send_notification') as mock_send:
                mock_send.return_value = {"status": "sent"}
                
                # Should not raise any exceptions
                process_notification(record)
    
    def test_invalid_notification_type(self):
        """Test invalid notification type."""
        record = {
            "messageId": "msg-invalid",
            "body": json.dumps({
                "incidentId": "INC-001",
                "type": "INVALID_TYPE",
                "target": "test",
                "message": "Test",
                "priority": "normal"
            })
        }
        
        with pytest.raises(ValueError):
            process_notification(record)
    
    def test_priority_validation(self):
        """Test notification priority validation."""
        valid_priorities = ['low', 'normal', 'high', 'critical']
        
        for priority in valid_priorities:
            notification = NotificationRequest(
                notification_id="test-001",
                incident_id="INC-001",
                type=NotificationType.SLACK,
                target="#test",
                message="Test",
                priority=priority
            )
            # Should not raise validation error
            assert notification.priority == priority
        
        # Test invalid priority
        with pytest.raises(ValueError):
            NotificationRequest(
                notification_id="test-001",
                incident_id="INC-001",
                type=NotificationType.SLACK,
                target="#test",
                message="Test",
                priority="invalid"
            )