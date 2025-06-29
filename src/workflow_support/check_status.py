"""
Check Status Lambda Function
Checks current incident status for Step Functions workflow.
"""

import os
from typing import Dict, Any
from datetime import datetime
import boto3
from aws_lambda_powertools import Logger
from aws_lambda_powertools.utilities.typing import LambdaContext

logger = Logger()

# Initialize DynamoDB client
dynamodb = boto3.resource('dynamodb')
table_name = os.environ.get('TABLE_NAME', 'aegis-incidents')
table = dynamodb.Table(table_name)


def get_incident_status(incident_id: str) -> Dict[str, Any]:
    """Get current incident status from DynamoDB."""
    try:
        response = table.get_item(
            Key={
                'PK': f'INCIDENT#{incident_id}',
                'SK': 'METADATA'
            }
        )
        
        if 'Item' not in response:
            raise ValueError(f"Incident {incident_id} not found")
        
        item = response['Item']
        
        # Calculate runtime
        created_at = datetime.fromisoformat(item['created_at'])
        runtime_seconds = (datetime.utcnow() - created_at).total_seconds()
        
        return {
            'status': item.get('status', 'UNKNOWN'),
            'severity': item.get('severity'),
            'createdAt': item.get('created_at'),
            'updatedAt': item.get('updated_at'),
            'runTime': int(runtime_seconds)
        }
        
    except Exception as e:
        logger.error(f"Failed to get incident status: {str(e)}")
        raise


@logger.inject_lambda_context
def handler(event: Dict[str, Any], context: LambdaContext) -> Dict[str, Any]:
    """
    Check incident status for workflow decisions.
    """
    incident_id = event.get('incidentId')
    
    if not incident_id:
        raise ValueError("Missing required field: incidentId")
    
    logger.info(f"Checking status for incident {incident_id}")
    
    status_info = get_incident_status(incident_id)
    
    logger.info("Status check complete", extra=status_info)
    
    return status_info