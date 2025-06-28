#!/usr/bin/env python3
"""Set up local DynamoDB tables for development."""

import boto3
from botocore.exceptions import ClientError

# Configuration
DYNAMODB_ENDPOINT = "http://localhost:8000"
REGION = "us-east-1"

# Create DynamoDB client
dynamodb = boto3.client(
    "dynamodb",
    endpoint_url=DYNAMODB_ENDPOINT,
    region_name=REGION,
    aws_access_key_id="local",
    aws_secret_access_key="local"
)


def create_incidents_table():
    """Create the main incidents table."""
    table_name = "aegis-local-incidents"
    
    try:
        print(f"Creating {table_name} table...")
        dynamodb.create_table(
            TableName=table_name,
            KeySchema=[
                {"AttributeName": "PK", "KeyType": "HASH"},
                {"AttributeName": "SK", "KeyType": "RANGE"}
            ],
            AttributeDefinitions=[
                {"AttributeName": "PK", "AttributeType": "S"},
                {"AttributeName": "SK", "AttributeType": "S"},
                {"AttributeName": "GSI1PK", "AttributeType": "S"},
                {"AttributeName": "GSI1SK", "AttributeType": "S"},
                {"AttributeName": "GSI2PK", "AttributeType": "S"},
                {"AttributeName": "GSI2SK", "AttributeType": "S"}
            ],
            GlobalSecondaryIndexes=[
                {
                    "IndexName": "GSI1",
                    "KeySchema": [
                        {"AttributeName": "GSI1PK", "KeyType": "HASH"},
                        {"AttributeName": "GSI1SK", "KeyType": "RANGE"}
                    ],
                    "Projection": {"ProjectionType": "ALL"},
                    "ProvisionedThroughput": {
                        "ReadCapacityUnits": 5,
                        "WriteCapacityUnits": 5
                    }
                },
                {
                    "IndexName": "GSI2",
                    "KeySchema": [
                        {"AttributeName": "GSI2PK", "KeyType": "HASH"},
                        {"AttributeName": "GSI2SK", "KeyType": "RANGE"}
                    ],
                    "Projection": {"ProjectionType": "ALL"},
                    "ProvisionedThroughput": {
                        "ReadCapacityUnits": 5,
                        "WriteCapacityUnits": 5
                    }
                }
            ],
            BillingMode="PROVISIONED",
            ProvisionedThroughput={
                "ReadCapacityUnits": 5,
                "WriteCapacityUnits": 5
            },
            StreamSpecification={
                "StreamEnabled": True,
                "StreamViewType": "NEW_AND_OLD_IMAGES"
            }
        )
        print(f"✓ {table_name} table created successfully")
    except ClientError as e:
        if e.response["Error"]["Code"] == "ResourceInUseException":
            print(f"! {table_name} table already exists")
        else:
            raise


def create_idempotency_table():
    """Create the idempotency table."""
    table_name = "aegis-local-idempotency"
    
    try:
        print(f"Creating {table_name} table...")
        dynamodb.create_table(
            TableName=table_name,
            KeySchema=[
                {"AttributeName": "id", "KeyType": "HASH"}
            ],
            AttributeDefinitions=[
                {"AttributeName": "id", "AttributeType": "S"}
            ],
            BillingMode="PAY_PER_REQUEST"
        )
        print(f"✓ {table_name} table created successfully")
    except ClientError as e:
        if e.response["Error"]["Code"] == "ResourceInUseException":
            print(f"! {table_name} table already exists")
        else:
            raise


def wait_for_tables():
    """Wait for all tables to be active."""
    tables = ["aegis-local-incidents", "aegis-local-idempotency"]
    
    print("\nWaiting for tables to become active...")
    for table_name in tables:
        waiter = dynamodb.get_waiter("table_exists")
        waiter.wait(TableName=table_name)
        print(f"✓ {table_name} is active")


def insert_sample_data():
    """Insert sample incident data for testing."""
    dynamodb_resource = boto3.resource(
        "dynamodb",
        endpoint_url=DYNAMODB_ENDPOINT,
        region_name=REGION,
        aws_access_key_id="local",
        aws_secret_access_key="local"
    )
    
    table = dynamodb_resource.Table("aegis-local-incidents")
    
    # Sample incident
    incident_id = "INC-001"
    
    items = [
        {
            "PK": f"INCIDENT#{incident_id}",
            "SK": "METADATA",
            "GSI1PK": "STATUS#OPEN",
            "GSI1SK": f"SEVERITY#P1#INCIDENT#{incident_id}",
            "title": "Sample Database Connection Error",
            "description": "Database connection pool exhausted",
            "status": "OPEN",
            "severity": "P1",
            "created_at": "2025-01-15T10:00:00Z",
            "updated_at": "2025-01-15T10:00:00Z"
        },
        {
            "PK": f"INCIDENT#{incident_id}",
            "SK": "EVENT#2025-01-15T10:00:00Z#001",
            "type": "INCIDENT_CREATED",
            "description": "Incident created",
            "source": "CloudWatch Alarm",
            "timestamp": "2025-01-15T10:00:00Z"
        },
        {
            "PK": f"INCIDENT#{incident_id}",
            "SK": "USER#user-001",
            "GSI2PK": "USER#user-001",
            "GSI2SK": f"INCIDENT#{incident_id}",
            "name": "John Doe",
            "role": "Incident Commander",
            "joined_at": "2025-01-15T10:01:00Z"
        }
    ]
    
    print("\nInserting sample data...")
    for item in items:
        table.put_item(Item=item)
    
    print("✓ Sample data inserted successfully")


def main():
    """Main function."""
    print("Setting up local DynamoDB tables for Aegis...\n")
    
    # Create tables
    create_incidents_table()
    create_idempotency_table()
    
    # Wait for tables to be ready
    wait_for_tables()
    
    # Insert sample data
    insert_sample_data()
    
    print("\n✅ Local DynamoDB setup complete!")
    print("\nYou can view the tables at: http://localhost:8001")


if __name__ == "__main__":
    main()