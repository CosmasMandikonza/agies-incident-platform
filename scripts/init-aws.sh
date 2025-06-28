#!/bin/bash
set -euo pipefail

echo "Initializing LocalStack AWS services..."

# Wait for LocalStack to be ready
sleep 10

# Create S3 buckets
echo "Creating S3 buckets..."
awslocal s3 mb s3://aegis-sam-artifacts-local
awslocal s3 mb s3://aegis-frontend-local

# Create EventBridge bus
echo "Creating EventBridge bus..."
awslocal events create-event-bus --name aegis-local-event-bus

# Create SQS queues
echo "Creating SQS queues..."
awslocal sqs create-queue --queue-name aegis-local-notifications
awslocal sqs create-queue --queue-name aegis-local-notifications-dlq
awslocal sqs create-queue --queue-name aegis-local-callback

# Create SNS topic
echo "Creating SNS topic..."
awslocal sns create-topic --name aegis-local-alarms

# Create Secrets Manager secret
echo "Creating secrets..."
awslocal secretsmanager create-secret \
    --name aegis-local-notification-secrets \
    --secret-string '{"slack_webhook":"https://hooks.slack.com/test","pagerduty_api_key":"test-key"}'

# Create Cognito User Pool
echo "Creating Cognito User Pool..."
awslocal cognito-idp create-user-pool \
    --pool-name aegis-local-users \
    --policies "PasswordPolicy={MinimumLength=8,RequireUppercase=true,RequireLowercase=true,RequireNumbers=true,RequireSymbols=true}"

echo "LocalStack initialization complete!"