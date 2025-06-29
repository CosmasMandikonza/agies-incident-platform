"""
Unit tests for Incident Ingestor Lambda function
"""

import json
import os
from datetime import datetime
from unittest.mock import Mock, patch, MagicMock
import pytest
from moto import mock_dynamodb, mock_events
import boto3

# Set environment variables before imports
os.environ['TABLE_NAME'] = 'test-incidents'
os.environ['EVENT_BUS_NAME'] = 'test-event-bus'
os.environ['AWS_DEFAULT_REGION'] = 'us-east-1'

from src.incident_ingestor.app import (
    handler,
    process_api_gateway_event,
    process_cloudwatch_alarm,
    create_incident
)
from shared.models import Incident, Severity
from aegis_shared.exceptions import ValidationError


@pytest.fixture
def api_gateway_event():
    """Sample API Gateway event."""
    return {
        "httpMethod": "POST",
        "path": "/incidents",
        "headers": {
            "Content-Type": "application/json",
            "Authorization": "Bearer test-token"
        },
        "body": json.dumps({
            "title": "Test Incident",
            "description": "Test description",
            "severity": "P2",
            "source": "Manual"
        }),
        "requestContext": {
            "requestId": "test-request-id",
            "identity": {
                "userArn": "arn:aws:iam::123456789012:user/test-user"
            }
        }
    }


@pytest.fixture
def cloudwatch_alarm_event():
    """Sample CloudWatch Alarm event."""
    return {
        "source": "aws.cloudwatch",
        "detail-type": "CloudWatch Alarm State Change",
        "detail": {
            "AlarmName": "High Error Rate - API Gateway",
            "AlarmDescription": "Error rate exceeds 5%",
            "NewStateValue": "ALARM",
            "NewStateReason": "Threshold crossed: 3 datapoints greater than 5%",
            "AlarmArn": "arn:aws:cloudwatch:us-east-1:123456789012:alarm:test-alarm",
            "Region": "us-east-1",
            "AWSAccountId": "123456789012",
            "Trigger": {
                "MetricName": "4XXError",
                "Namespace": "AWS/ApiGateway"
            }
        }
    }


@pytest.fixture
def lambda_context():
    """Mock Lambda context."""
    context = Mock()
    context.request_id = "test-request-id"
    context.function_name = "test-function"
    context.memory_limit_in_mb = 1024
    context.aws_request_id = "test-aws-request-id"
    return context


@pytest.fixture
def mock_clients():
    """Mock AWS clients."""
    with mock_dynamodb(), mock_events():
        # Create DynamoDB table
        dynamodb = boto3.resource('dynamodb', region_name='us-east-1')
        table = dynamodb.create_table(
            TableName='test-incidents',
            KeySchema=[
                {'AttributeName': 'PK', 'KeyType': 'HASH'},
                {'AttributeName': 'SK', 'KeyType': 'RANGE'}
            ],
            AttributeDefinitions=[
                {'AttributeName': 'PK', 'AttributeType': 'S'},
                {'AttributeName': 'SK', 'AttributeType': 'S'}
            ],
            BillingMode='PAY_PER_REQUEST'
        )
        
        # Create EventBridge bus
        events_client = boto3.client('events', region_name='us-east-1')
        events_client.create_event_bus(Name='test-event-bus')
        
        yield {
            'dynamodb_table': table,
            'events_client': events_client
        }


class TestIncidentIngestor:
    """Test cases for incident ingestor."""
    
    def test_handler_api_gateway_success(self, api_gateway_event, lambda_context, mock_clients):
        """Test successful incident creation via API Gateway."""
        response = handler(api_gateway_event, lambda_context)
        
        assert response['statusCode'] == 201
        body = json.loads(response['body'])
        assert 'incidentId' in body
        assert body['title'] == 'Test Incident'
        assert body['severity'] == 'P2'
        assert body['status'] == 'OPEN'
    
    def test_handler_api_gateway_invalid_input(self, api_gateway_event, lambda_context, mock_clients):
        """Test API Gateway with invalid input."""
        # Missing required field
        invalid_event = api_gateway_event.copy()
        invalid_event['body'] = json.dumps({
            "description": "Missing title"
        })
        
        response = handler(invalid_event, lambda_context)
        
        assert response['statusCode'] == 400
        body = json.loads(response['body'])
        assert 'error' in body
    
    def test_handler_api_gateway_invalid_json(self, api_gateway_event, lambda_context, mock_clients):
        """Test API Gateway with invalid JSON."""
        invalid_event = api_gateway_event.copy()
        invalid_event['body'] = "invalid json{"
        
        response = handler(invalid_event, lambda_context)
        
        assert response['statusCode'] == 400
        body = json.loads(response['body'])
        assert 'Invalid JSON' in body['error']
    
    def test_handler_cloudwatch_alarm(self, cloudwatch_alarm_event, lambda_context, mock_clients):
        """Test CloudWatch Alarm processing."""
        response = handler(cloudwatch_alarm_event, lambda_context)
        
        assert response['statusCode'] == 200
        body = json.loads(response['body'])
        assert 'incidentId' in body
    
    def test_handler_cloudwatch_alarm_not_alarm_state(self, cloudwatch_alarm_event, lambda_context, mock_clients):
        """Test CloudWatch Alarm with non-ALARM state."""
        event = cloudwatch_alarm_event.copy()
        event['detail']['NewStateValue'] = 'OK'
        
        response = handler(event, lambda_context)
        
        assert response['statusCode'] == 200
        body = json.loads(response['body'])
        assert body['message'] == 'Alarm state not actionable'
    
    def test_process_api_gateway_event_validation(self):
        """Test API Gateway event processing with validation."""
        # Valid input
        valid_input = {
            "title": "Test Incident",
            "severity": "P1",
            "source": "Manual"
        }
        
        with patch('src.incident_ingestor.app.create_incident') as mock_create:
            mock_create.return_value = {"incidentId": "INC-123"}
            result = process_api_gateway_event(valid_input)
            assert result['incidentId'] == 'INC-123'
    
    def test_process_api_gateway_event_p0_requires_description(self):
        """Test P0 incidents require description."""
        invalid_input = {
            "title": "Critical Incident",
            "severity": "P0",
            "source": "Manual"
        }
        
        with pytest.raises(ValidationError) as exc_info:
            process_api_gateway_event(invalid_input)
        
        assert "P0 incidents must have a description" in str(exc_info.value)
    
    def test_process_cloudwatch_alarm_severity_mapping(self):
        """Test CloudWatch alarm severity mapping."""
        # Test P0 mapping
        alarm_data = {
            "AlarmName": "CRITICAL Database Connection Failed",
            "AlarmDescription": "Critical issue",
            "NewStateValue": "ALARM",
            "NewStateReason": "Connection failed"
        }
        
        with patch('src.incident_ingestor.app.create_incident') as mock_create:
            mock_create.return_value = {"incidentId": "INC-123", "severity": "P0"}
            result = process_cloudwatch_alarm(alarm_data)
            
            # Verify P0 severity was assigned
            call_args = mock_create.call_args[0][0]
            assert call_args.severity == "P0"
    
    @mock_dynamodb
    @mock_events
    def test_create_incident_success(self):
        """Test successful incident creation."""
        # Setup mocks
        dynamodb = boto3.resource('dynamodb', region_name='us-east-1')
        dynamodb.create_table(
            TableName='test-incidents',
            KeySchema=[
                {'AttributeName': 'PK', 'KeyType': 'HASH'},
                {'AttributeName': 'SK', 'KeyType': 'RANGE'}
            ],
            AttributeDefinitions=[
                {'AttributeName': 'PK', 'AttributeType': 'S'},
                {'AttributeName': 'SK', 'AttributeType': 'S'}
            ],
            BillingMode='PAY_PER_REQUEST'
        )
        
        events_client = boto3.client('events', region_name='us-east-1')
        events_client.create_event_bus(Name='test-event-bus')
        
        # Create incident
        incident = Incident(
            id="INC-TEST-001",
            title="Test Incident",
            severity=Severity.P2,
            source="Test"
        )
        
        with patch('src.incident_ingestor.app.dynamodb_client') as mock_db, \
             patch('src.incident_ingestor.app.event_publisher') as mock_publisher:
            
            mock_db.batch_write_items.return_value = None
            mock_publisher.publish_batch_events.return_value = None
            
            result = create_incident(incident)
            
            assert result['incidentId'] == 'INC-TEST-001'
            assert result['title'] == 'Test Incident'
            assert result['severity'] == 'P2'
            assert result['status'] == 'OPEN'
            
            # Verify database write was called
            mock_db.batch_write_items.assert_called_once()
            
            # Verify events were published
            mock_publisher.publish_batch_events.assert_called_once()
    
    def test_create_incident_database_error(self):
        """Test incident creation with database error."""
        incident = Incident(
            id="INC-TEST-001",
            title="Test Incident",
            severity=Severity.P2,
            source="Test"
        )
        
        with patch('src.incident_ingestor.app.dynamodb_client') as mock_db:
            mock_db.batch_write_items.side_effect = Exception("Database error")
            
            with pytest.raises(Exception) as exc_info:
                create_incident(incident)
            
            assert "Database error" in str(exc_info.value)


class TestIncidentValidation:
    """Test cases for incident validation."""
    
    def test_valid_severities(self):
        """Test all valid severity levels."""
        for severity in ['P0', 'P1', 'P2', 'P3', 'P4']:
            input_data = {
                "title": f"Test {severity} Incident",
                "severity": severity,
                "source": "Test"
            }
            
            with patch('src.incident_ingestor.app.create_incident') as mock_create:
                mock_create.return_value = {"incidentId": "INC-123"}
                result = process_api_gateway_event(input_data)
                assert result['incidentId'] == 'INC-123'
    
    def test_invalid_severity(self):
        """Test invalid severity level."""
        input_data = {
            "title": "Test Incident",
            "severity": "P5",  # Invalid
            "source": "Test"
        }
        
        with pytest.raises(ValidationError):
            process_api_gateway_event(input_data)
    
    def test_title_length_validation(self):
        """Test title length constraints."""
        # Too short
        with pytest.raises(ValidationError):
            process_api_gateway_event({
                "title": "",
                "severity": "P2",
                "source": "Test"
            })
        
        # Too long
        with pytest.raises(ValidationError):
            process_api_gateway_event({
                "title": "x" * 201,  # Max is 200
                "severity": "P2",
                "source": "Test"
            })
    
    def test_metadata_validation(self):
        """Test metadata field validation."""
        input_data = {
            "title": "Test Incident",
            "severity": "P2",
            "source": "Test",
            "metadata": {
                "service": "api-gateway",
                "region": "us-east-1",
                "custom_field": "value"
            }
        }
        
        with patch('src.incident_ingestor.app.create_incident') as mock_create:
            mock_create.return_value = {"incidentId": "INC-123"}
            result = process_api_gateway_event(input_data)
            assert result['incidentId'] == 'INC-123'


class TestCloudWatchIntegration:
    """Test cases for CloudWatch alarm integration."""
    
    def test_alarm_severity_patterns(self):
        """Test different alarm patterns map to correct severities."""
        test_cases = [
            ("p0-database-failure", "P0"),
            ("High CPU Utilization", "P1"),
            ("Moderate Error Rate", "P2"),
            ("Low Priority Alert", "P2")  # Default
        ]
        
        for alarm_name, expected_severity in test_cases:
            alarm_data = {
                "AlarmName": alarm_name,
                "AlarmDescription": "Test",
                "NewStateValue": "ALARM",
                "NewStateReason": "Test reason"
            }
            
            with patch('src.incident_ingestor.app.create_incident') as mock_create:
                mock_create.return_value = {"incidentId": "INC-123"}
                process_cloudwatch_alarm(alarm_data)
                
                call_args = mock_create.call_args[0][0]
                assert call_args.severity == expected_severity
    
    def test_alarm_metadata_extraction(self):
        """Test metadata extraction from CloudWatch alarm."""
        alarm_data = {
            "AlarmName": "Test Alarm",
            "AlarmDescription": "Test description",
            "NewStateValue": "ALARM",
            "NewStateReason": "Threshold crossed",
            "AlarmArn": "arn:aws:cloudwatch:us-east-1:123456789012:alarm:test",
            "Region": "us-east-1",
            "AWSAccountId": "123456789012",
            "Trigger": {
                "MetricName": "CPUUtilization",
                "Namespace": "AWS/EC2"
            }
        }
        
        with patch('src.incident_ingestor.app.create_incident') as mock_create:
            mock_create.return_value = {"incidentId": "INC-123"}
            process_cloudwatch_alarm(alarm_data)
            
            call_args = mock_create.call_args[0][0]
            assert call_args.metadata['alarm_name'] == "Test Alarm"
            assert call_args.metadata['region'] == "us-east-1"
            assert call_args.metadata['metric_name'] == "CPUUtilization"
            assert call_args.metadata['namespace'] == "AWS/EC2"