# Aegis Stack Outputs Reference

This document describes all CloudFormation stack outputs that are exported by the Aegis infrastructure.

## API Endpoints

### ApiUrl
- **Description**: REST API Gateway endpoint URL
- **Export Name**: `${StackName}-ApiUrl`
- **Example**: `https://abcd1234.execute-api.us-east-1.amazonaws.com/dev`
- **Usage**: Base URL for all REST API calls

### GraphQLEndpoint
- **Description**: AppSync GraphQL API endpoint
- **Export Name**: `${StackName}-GraphQLEndpoint`
- **Example**: `https://abcd1234.appsync-api.us-east-1.amazonaws.com/graphql`
- **Usage**: GraphQL API endpoint for real-time subscriptions

## Event Infrastructure

### EventBusName
- **Description**: Name of the central EventBridge event bus
- **Export Name**: `${StackName}-EventBusName`
- **Example**: `aegis-dev-event-bus`
- **Usage**: Publishing custom events to the platform

## Data Storage

### IncidentsTableName
- **Description**: Name of the main DynamoDB incidents table
- **Export Name**: `${StackName}-IncidentsTableName`
- **Example**: `aegis-dev-incidents`
- **Usage**: Direct table access for advanced queries

### IncidentsTableStreamArn
- **Description**: ARN of the DynamoDB stream for real-time changes
- **Export Name**: `${StackName}-StreamArn`
- **Example**: `arn:aws:dynamodb:us-east-1:123456789012:table/aegis-dev-incidents/stream/2025-01-01T00:00:00.000`
- **Usage**: Connecting additional stream processors

## Authentication

### UserPoolId
- **Description**: Cognito User Pool ID for authentication
- **Export Name**: `${StackName}-UserPoolId`
- **Example**: `us-east-1_abcd1234`
- **Usage**: User management and authentication flows

### UserPoolClientId
- **Description**: Cognito User Pool Client ID for web application
- **Export Name**: `${StackName}-UserPoolClientId`
- **Example**: `1234567890abcdefghijklmnop`
- **Usage**: Frontend authentication configuration

## Workflow

### StateMachineArn
- **Description**: ARN of the incident lifecycle Step Functions state machine
- **Export Name**: `${StackName}-StateMachineArn`
- **Example**: `arn:aws:states:us-east-1:123456789012:stateMachine:aegis-dev-incident-workflow`
- **Usage**: Starting new workflow executions

## Queues

### NotificationQueueUrl
- **Description**: URL of the notification processing queue
- **Export Name**: `${StackName}-NotificationQueueUrl`
- **Example**: `https://sqs.us-east-1.amazonaws.com/123456789012/aegis-dev-notifications`
- **Usage**: Sending notifications to external services

### NotificationDLQUrl
- **Description**: URL of the notification dead letter queue
- **Export Name**: `${StackName}-NotificationDLQUrl`
- **Example**: `https://sqs.us-east-1.amazonaws.com/123456789012/aegis-dev-notifications-dlq`
- **Usage**: Monitoring failed notifications

## Usage Examples

### Retrieving Outputs via AWS CLI

```bash
# Get a specific output value
aws cloudformation describe-stacks \
    --stack-name aegis-dev \
    --query 'Stacks[0].Outputs[?OutputKey==`ApiUrl`].OutputValue' \
    --output text

# Get all outputs as JSON
aws cloudformation describe-stacks \
    --stack-name aegis-dev \
    --query 'Stacks[0].Outputs' \
    --output json
```

### Using Outputs in Other Stacks

```yaml
Resources:
  MyFunction:
    Type: AWS::Lambda::Function
    Properties:
      Environment:
        Variables:
          AEGIS_API_URL: !ImportValue aegis-dev-ApiUrl
          AEGIS_TABLE_NAME: !ImportValue aegis-dev-IncidentsTableName
```

### Environment Variables for Frontend

```javascript
// .env.production
REACT_APP_API_ENDPOINT=${ApiUrl}
REACT_APP_GRAPHQL_ENDPOINT=${GraphQLEndpoint}
REACT_APP_USER_POOL_ID=${UserPoolId}
REACT_APP_USER_POOL_CLIENT_ID=${UserPoolClientId}
```