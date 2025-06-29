"""
Integration tests for complete incident workflow
"""

import os
import json
import time
from datetime import datetime
from unittest.mock import patch
import pytest
import boto3
import requests
from moto import mock_dynamodb, mock_events, mock_sqs, mock_stepfunctions

# Test configuration
API_ENDPOINT = os.environ.get('API_ENDPOINT', 'http://localhost:3000')
TEST_TIMEOUT = 30  # seconds


@pytest.fixture(scope='module')
def aws_resources():
    """Set up AWS resources for integration tests."""
    with mock_dynamodb(), mock_events(), mock_sqs(), mock_stepfunctions():
        # Create DynamoDB table
        dynamodb = boto3.resource('dynamodb', region_name='us-east-1')
        table = dynamodb.create_table(
            TableName='aegis-test-incidents',
            KeySchema=[
                {'AttributeName': 'PK', 'KeyType': 'HASH'},
                {'AttributeName': 'SK', 'KeyType': 'RANGE'}
            ],
            AttributeDefinitions=[
                {'AttributeName': 'PK', 'AttributeType': 'S'},
                {'AttributeName': 'SK', 'AttributeType': 'S'},
                {'AttributeName': 'GSI1PK', 'AttributeType': 'S'},
                {'AttributeName': 'GSI1SK', 'AttributeType': 'S'}
            ],
            GlobalSecondaryIndexes=[{
                'IndexName': 'GSI1',
                'KeySchema': [
                    {'AttributeName': 'GSI1PK', 'KeyType': 'HASH'},
                    {'AttributeName': 'GSI1SK', 'KeyType': 'RANGE'}
                ],
                'Projection': {'ProjectionType': 'ALL'},
                'ProvisionedThroughput': {
                    'ReadCapacityUnits': 5,
                    'WriteCapacityUnits': 5
                }
            }],
            BillingMode='PROVISIONED',
            ProvisionedThroughput={
                'ReadCapacityUnits': 10,
                'WriteCapacityUnits': 10
            },
            StreamSpecification={
                'StreamEnabled': True,
                'StreamViewType': 'NEW_AND_OLD_IMAGES'
            }
        )
        
        # Create EventBridge bus
        events = boto3.client('events', region_name='us-east-1')
        events.create_event_bus(Name='aegis-test-event-bus')
        
        # Create SQS queues
        sqs = boto3.resource('sqs', region_name='us-east-1')
        notification_queue = sqs.create_queue(
            QueueName='aegis-test-notifications',
            Attributes={
                'VisibilityTimeout': '300',
                'MessageRetentionPeriod': '1209600'
            }
        )
        
        dlq = sqs.create_queue(
            QueueName='aegis-test-notifications-dlq',
            Attributes={
                'MessageRetentionPeriod': '1209600'
            }
        )
        
        callback_queue = sqs.create_queue(
            QueueName='aegis-test-callback',
            Attributes={
                'VisibilityTimeout': '60'
            }
        )
        
        yield {
            'dynamodb_table': table,
            'event_bus': events,
            'notification_queue': notification_queue,
            'dlq': dlq,
            'callback_queue': callback_queue
        }


class TestIncidentCreationFlow:
    """Test complete incident creation flow."""
    
    def test_create_incident_via_api(self, aws_resources):
        """Test creating incident through API Gateway."""
        # Create incident
        incident_data = {
            "title": "Integration Test - API Gateway Error",
            "description": "High error rate detected on API Gateway",
            "severity": "P1",
            "source": "Integration Test",
            "metadata": {
                "service": "api-gateway",
                "error_rate": 15.5,
                "region": "us-east-1"
            }
        }
        
        response = requests.post(
            f"{API_ENDPOINT}/incidents",
            json=incident_data,
            headers={
                "Content-Type": "application/json",
                "Authorization": "Bearer test-token"
            }
        )
        
        assert response.status_code == 201
        result = response.json()
        
        # Verify response structure
        assert 'incidentId' in result
        assert result['title'] == incident_data['title']
        assert result['severity'] == 'P1'
        assert result['status'] == 'OPEN'
        
        incident_id = result['incidentId']
        
        # Verify incident was stored in DynamoDB
        table = aws_resources['dynamodb_table']
        stored_incident = table.get_item(
            Key={
                'PK': f'INCIDENT#{incident_id}',
                'SK': 'METADATA'
            }
        )
        
        assert 'Item' in stored_incident
        assert stored_incident['Item']['title'] == incident_data['title']
        
        # Verify timeline event was created
        timeline_events = table.query(
            KeyConditionExpression='PK = :pk AND begins_with(SK, :sk)',
            ExpressionAttributeValues={
                ':pk': f'INCIDENT#{incident_id}',
                ':sk': 'EVENT#'
            }
        )
        
        assert timeline_events['Count'] > 0
        assert any(event['type'] == 'INCIDENT_CREATED' for event in timeline_events['Items'])
        
        return incident_id
    
    def test_create_incident_from_cloudwatch(self, aws_resources):
        """Test incident creation from CloudWatch alarm."""
        # Simulate CloudWatch alarm event
        alarm_event = {
            "source": "aws.cloudwatch",
            "detail-type": "CloudWatch Alarm State Change",
            "detail": {
                "AlarmName": "High CPU Utilization - Production",
                "AlarmDescription": "CPU usage above 80%",
                "NewStateValue": "ALARM",
                "NewStateReason": "Threshold crossed: 5 datapoints greater than 80%",
                "AlarmArn": "arn:aws:cloudwatch:us-east-1:123456789012:alarm:test",
                "Trigger": {
                    "MetricName": "CPUUtilization",
                    "Namespace": "AWS/EC2"
                }
            }
        }
        
        # Publish event to EventBridge
        events = aws_resources['event_bus']
        events.put_events(
            Entries=[{
                'Source': alarm_event['source'],
                'DetailType': alarm_event['detail-type'],
                'Detail': json.dumps(alarm_event['detail']),
                'EventBusName': 'aegis-test-event-bus'
            }]
        )
        
        # Wait for processing
        time.sleep(2)
        
        # Verify incident was created
        table = aws_resources['dynamodb_table']
        response = table.query(
            IndexName='GSI1',
            KeyConditionExpression='GSI1PK = :pk',
            ExpressionAttributeValues={
                ':pk': 'STATUS#OPEN'
            }
        )
        
        # Find our incident
        created_incident = None
        for item in response['Items']:
            if 'High CPU Utilization' in item.get('title', ''):
                created_incident = item
                break
        
        assert created_incident is not None
        assert created_incident['source'] == 'CloudWatch Alarms'
        assert 'CPU usage above 80%' in created_incident['description']


class TestIncidentLifecycle:
    """Test incident lifecycle management."""
    
    def test_acknowledge_incident(self, aws_resources):
        """Test acknowledging an incident."""
        # First create an incident
        incident_id = TestIncidentCreationFlow().test_create_incident_via_api(aws_resources)
        
        # Acknowledge the incident
        response = requests.post(
            f"{API_ENDPOINT}/incidents/{incident_id}/acknowledge",
            headers={"Authorization": "Bearer test-token"}
        )
        
        assert response.status_code == 200
        result = response.json()
        assert result['status'] == 'ACKNOWLEDGED'
        assert 'acknowledgedAt' in result
        
        # Verify status in database
        table = aws_resources['dynamodb_table']
        incident = table.get_item(
            Key={
                'PK': f'INCIDENT#{incident_id}',
                'SK': 'METADATA'
            }
        )
        
        assert incident['Item']['status'] == 'ACKNOWLEDGED'
        assert 'acknowledged_at' in incident['Item']
    
    def test_update_incident_status(self, aws_resources):
        """Test updating incident status through lifecycle."""
        # Create incident
        incident_id = TestIncidentCreationFlow().test_create_incident_via_api(aws_resources)
        
        # Test status transitions
        transitions = [
            ('ACKNOWLEDGED', 'Acknowledging incident'),
            ('MITIGATING', 'Starting mitigation'),
            ('RESOLVED', 'Issue has been resolved'),
            ('CLOSED', 'Closing incident')
        ]
        
        for new_status, reason in transitions:
            response = requests.patch(
                f"{API_ENDPOINT}/incidents/{incident_id}/status",
                json={
                    "status": new_status,
                    "reason": reason
                },
                headers={"Authorization": "Bearer test-token"}
            )
            
            assert response.status_code == 200
            result = response.json()
            assert result['status'] == new_status
            
            # Verify timeline event was created
            table = aws_resources['dynamodb_table']
            timeline = table.query(
                KeyConditionExpression='PK = :pk AND begins_with(SK, :sk)',
                ExpressionAttributeValues={
                    ':pk': f'INCIDENT#{incident_id}',
                    ':sk': 'EVENT#'
                }
            )
            
            # Check for status change event
            status_events = [
                e for e in timeline['Items'] 
                if e.get('type') == 'STATUS_CHANGED' and new_status in e.get('description', '')
            ]
            assert len(status_events) > 0
    
    def test_add_comment(self, aws_resources):
        """Test adding comments to incident."""
        # Create incident
        incident_id = TestIncidentCreationFlow().test_create_incident_via_api(aws_resources)
        
        # Add comment
        comment_text = "I'm investigating the root cause"
        response = requests.post(
            f"{API_ENDPOINT}/incidents/{incident_id}/comments",
            json={"text": comment_text},
            headers={"Authorization": "Bearer test-token"}
        )
        
        assert response.status_code == 201
        result = response.json()
        assert result['text'] == comment_text
        assert 'timestamp' in result
        
        # Verify comment in database
        table = aws_resources['dynamodb_table']
        comments = table.query(
            KeyConditionExpression='PK = :pk AND begins_with(SK, :sk)',
            ExpressionAttributeValues={
                ':pk': f'INCIDENT#{incident_id}',
                ':sk': 'COMMENT#'
            }
        )
        
        assert comments['Count'] > 0
        assert any(c['text'] == comment_text for c in comments['Items'])


class TestNotificationFlow:
    """Test notification delivery flow."""
    
    def test_p0_incident_notifications(self, aws_resources):
        """Test P0 incident triggers immediate notifications."""
        # Create P0 incident
        incident_data = {
            "title": "CRITICAL: Database Connection Lost",
            "description": "Primary database is unreachable",
            "severity": "P0",
            "source": "Integration Test"
        }
        
        response = requests.post(
            f"{API_ENDPOINT}/incidents",
            json=incident_data,
            headers={"Authorization": "Bearer test-token"}
        )
        
        assert response.status_code == 201
        incident_id = response.json()['incidentId']
        
        # Check notification queue
        queue = aws_resources['notification_queue']
        
        # Wait for messages
        time.sleep(3)
        
        messages = queue.receive_messages(MaxNumberOfMessages=10)
        
        # Verify critical notifications were sent
        notification_types = []
        for message in messages:
            body = json.loads(message.body)
            notification_types.append(body['type'])
            
            # Verify P0 specific attributes
            if body['type'] == 'PAGE':
                assert body['priority'] == 'critical'
            if body['type'] == 'SLACK':
                assert body['target'] == '#incidents-p0'
        
        # P0 should trigger both page and Slack
        assert 'PAGE' in notification_types
        assert 'SLACK' in notification_types
    
    def test_notification_retry_on_failure(self, aws_resources):
        """Test notification retry mechanism."""
        # Mock external service failure
        with patch('httpx.Client.post') as mock_post:
            mock_post.side_effect = Exception("Service unavailable")
            
            # Create incident
            incident_data = {
                "title": "Test Retry Mechanism",
                "severity": "P2",
                "source": "Integration Test"
            }
            
            response = requests.post(
                f"{API_ENDPOINT}/incidents",
                json=incident_data,
                headers={"Authorization": "Bearer test-token"}
            )
            
            incident_id = response.json()['incidentId']
            
            # Wait for initial processing
            time.sleep(5)
            
            # Check DLQ for failed messages
            dlq = aws_resources['dlq']
            messages = dlq.receive_messages(MaxNumberOfMessages=10)
            
            # Should have messages in DLQ after retries
            assert len(messages) > 0


class TestAIIntegration:
    """Test AI-powered features."""
    
    @patch('boto3.client')
    def test_ai_summary_generation(self, mock_boto, aws_resources):
        """Test AI summary generation for incidents."""
        # Mock Bedrock response
        mock_bedrock = mock_boto.return_value
        mock_bedrock.invoke_model.return_value = {
            'body': json.dumps({
                'content': [{
                    'text': 'Summary: Database connection issues detected. Team investigating root cause.'
                }],
                'usage': {
                    'input_tokens': 100,
                    'output_tokens': 50
                }
            }).encode()
        }
        
        # Create incident with activity
        incident_id = TestIncidentCreationFlow().test_create_incident_via_api(aws_resources)
        
        # Add some timeline events
        for i in range(5):
            requests.post(
                f"{API_ENDPOINT}/incidents/{incident_id}/comments",
                json={"text": f"Update {i}: Still investigating"},
                headers={"Authorization": "Bearer test-token"}
            )
        
        # Trigger AI summary
        response = requests.post(
            f"{API_ENDPOINT}/incidents/{incident_id}/generate-summary",
            headers={"Authorization": "Bearer test-token"}
        )
        
        assert response.status_code == 200
        
        # Wait for processing
        time.sleep(3)
        
        # Check for AI summary in database
        table = aws_resources['dynamodb_table']
        summaries = table.query(
            KeyConditionExpression='PK = :pk AND begins_with(SK, :sk)',
            ExpressionAttributeValues={
                ':pk': f'INCIDENT#{incident_id}',
                ':sk': 'SUMMARY#'
            }
        )
        
        assert summaries['Count'] > 0
        assert 'Database connection issues' in summaries['Items'][0]['summary_text']