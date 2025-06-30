"""DynamoDB client wrapper for Aegis platform."""

from typing import Optional, List, Dict, Any, Tuple
import boto3
from boto3.dynamodb.conditions import Key, Attr
from botocore.exceptions import ClientError
from aws_lambda_powertools import Logger, Tracer
from shared.exceptions import IncidentNotFoundError, AegisError
from shared.utils import deserialize_from_dynamodb, serialize_for_dynamodb

logger = Logger()
tracer = Tracer()


class DynamoDBClient:
    """Wrapper for DynamoDB operations."""
    
    def __init__(self, table_name: str, region: Optional[str] = None):
        """Initialize DynamoDB client."""
        self.table_name = table_name
        self.region = region or "us-east-1"
        
        # Initialize boto3 resources
        self.dynamodb = boto3.resource("dynamodb", region_name=self.region)
        self.table = self.dynamodb.Table(table_name)
        
        logger.info(f"Initialized DynamoDB client for table: {table_name}")
    
    @tracer.capture_method
    def put_item(self, item: Dict[str, Any], condition_expression: Optional[str] = None) -> None:
        """Put an item into DynamoDB."""
        try:
            kwargs = {
                "Item": serialize_for_dynamodb(item)
            }
            if condition_expression:
                kwargs["ConditionExpression"] = condition_expression
            
            self.table.put_item(**kwargs)
            logger.info("Item successfully written to DynamoDB", extra={"pk": item.get("PK"), "sk": item.get("SK")})
        except ClientError as e:
            error_code = e.response["Error"]["Code"]
            if error_code == "ConditionalCheckFailedException":
                logger.warning("Conditional check failed", extra={"error": str(e)})
                raise
            logger.error(f"Failed to put item: {str(e)}", extra={"error": str(e)})
            raise AegisError(f"Failed to write to DynamoDB: {str(e)}")
    
    @tracer.capture_method
    def get_item(self, pk: str, sk: str) -> Optional[Dict[str, Any]]:
        """Get a single item from DynamoDB."""
        try:
            response = self.table.get_item(
                Key={
                    "PK": pk,
                    "SK": sk
                }
            )
            
            if "Item" in response:
                item = deserialize_from_dynamodb(response["Item"])
                logger.info("Item retrieved from DynamoDB", extra={"pk": pk, "sk": sk})
                return item
            
            logger.info("Item not found", extra={"pk": pk, "sk": sk})
            return None
            
        except ClientError as e:
            logger.error(f"Failed to get item: {str(e)}", extra={"error": str(e)})
            raise AegisError(f"Failed to read from DynamoDB: {str(e)}")
    
    @tracer.capture_method
    def query_by_pk(self, pk: str, sk_prefix: Optional[str] = None, 
                    limit: Optional[int] = None) -> List[Dict[str, Any]]:
        """Query items by partition key with optional sort key prefix."""
        try:
            key_condition = Key("PK").eq(pk)
            if sk_prefix:
                key_condition = key_condition & Key("SK").begins_with(sk_prefix)
            
            kwargs = {
                "KeyConditionExpression": key_condition,
                "ScanIndexForward": True  # Sort by SK ascending
            }
            
            if limit:
                kwargs["Limit"] = limit
            
            response = self.table.query(**kwargs)
            items = [deserialize_from_dynamodb(item) for item in response.get("Items", [])]
            
            logger.info(f"Query returned {len(items)} items", extra={"pk": pk, "sk_prefix": sk_prefix})
            return items
            
        except ClientError as e:
            logger.error(f"Failed to query items: {str(e)}", extra={"error": str(e)})
            raise AegisError(f"Failed to query DynamoDB: {str(e)}")
    
    @tracer.capture_method
    def query_gsi(self, index_name: str, pk_value: str, sk_value: Optional[str] = None,
                  sk_condition: Optional[str] = None, limit: Optional[int] = None) -> Tuple[List[Dict[str, Any]], Optional[str]]:
        """Query a Global Secondary Index."""
        try:
            key_condition = Key(f"{index_name}PK").eq(pk_value)
            
            if sk_value:
                if sk_condition == "begins_with":
                    key_condition = key_condition & Key(f"{index_name}SK").begins_with(sk_value)
                else:
                    key_condition = key_condition & Key(f"{index_name}SK").eq(sk_value)
            
            kwargs = {
                "IndexName": index_name,
                "KeyConditionExpression": key_condition
            }
            
            if limit:
                kwargs["Limit"] = limit
            
            response = self.table.query(**kwargs)
            items = [deserialize_from_dynamodb(item) for item in response.get("Items", [])]
            next_token = response.get("LastEvaluatedKey")
            
            logger.info(f"GSI query returned {len(items)} items", 
                       extra={"index": index_name, "pk": pk_value})
            
            return items, next_token
            
        except ClientError as e:
            logger.error(f"Failed to query GSI: {str(e)}", extra={"error": str(e)})
            raise AegisError(f"Failed to query DynamoDB GSI: {str(e)}")
    
    @tracer.capture_method
    def update_item(self, pk: str, sk: str, updates: Dict[str, Any], 
                    condition_expression: Optional[str] = None) -> Dict[str, Any]:
        """Update an item in DynamoDB."""
        try:
            # Build update expression
            update_parts = []
            expression_values = {}
            expression_names = {}
            
            for key, value in updates.items():
                # Use expression attribute names to handle reserved keywords
                safe_key = f"#{key}"
                expression_names[safe_key] = key
                
                update_parts.append(f"{safe_key} = :val_{key}")
                expression_values[f":val_{key}"] = serialize_for_dynamodb(value)
            
            update_expression = "SET " + ", ".join(update_parts)
            
            kwargs = {
                "Key": {"PK": pk, "SK": sk},
                "UpdateExpression": update_expression,
                "ExpressionAttributeValues": expression_values,
                "ExpressionAttributeNames": expression_names,
                "ReturnValues": "ALL_NEW"
            }
            
            if condition_expression:
                kwargs["ConditionExpression"] = condition_expression
            
            response = self.table.update_item(**kwargs)
            updated_item = deserialize_from_dynamodb(response["Attributes"])
            
            logger.info("Item updated successfully", extra={"pk": pk, "sk": sk})
            return updated_item
            
        except ClientError as e:
            error_code = e.response["Error"]["Code"]
            if error_code == "ConditionalCheckFailedException":
                logger.warning("Conditional check failed during update", extra={"error": str(e)})
                raise
            logger.error(f"Failed to update item: {str(e)}", extra={"error": str(e)})
            raise AegisError(f"Failed to update DynamoDB item: {str(e)}")
    
    @tracer.capture_method
    def batch_write_items(self, items: List[Dict[str, Any]]) -> None:
        """Batch write multiple items to DynamoDB."""
        try:
            with self.table.batch_writer() as batch:
                for item in items:
                    batch.put_item(Item=serialize_for_dynamodb(item))
            
            logger.info(f"Batch wrote {len(items)} items")
            
        except ClientError as e:
            logger.error(f"Failed to batch write items: {str(e)}", extra={"error": str(e)})
            raise AegisError(f"Failed to batch write to DynamoDB: {str(e)}")
    
    @tracer.capture_method
    def delete_item(self, pk: str, sk: str, condition_expression: Optional[str] = None) -> None:
        """Delete an item from DynamoDB."""
        try:
            kwargs = {
                "Key": {"PK": pk, "SK": sk}
            }
            
            if condition_expression:
                kwargs["ConditionExpression"] = condition_expression
            
            self.table.delete_item(**kwargs)
            logger.info("Item deleted successfully", extra={"pk": pk, "sk": sk})
            
        except ClientError as e:
            error_code = e.response["Error"]["Code"]
            if error_code == "ConditionalCheckFailedException":
                logger.warning("Conditional check failed during delete", extra={"error": str(e)})
                raise
            logger.error(f"Failed to delete item: {str(e)}", extra={"error": str(e)})
            raise AegisError(f"Failed to delete from DynamoDB: {str(e)}")
    
    def get_incident(self, incident_id: str) -> Dict[str, Any]:
        """Get all items related to an incident."""
        pk = f"INCIDENT#{incident_id}"
        items = self.query_by_pk(pk)
        
        if not items:
            raise IncidentNotFoundError(f"Incident {incident_id} not found")
        
        # Organize items by type
        incident_data = {
            "metadata": None,
            "timeline": [],
            "comments": [],
            "participants": [],
            "summaries": []
        }
        
        for item in items:
            sk = item.get("SK", "")
            if sk == "METADATA":
                incident_data["metadata"] = item
            elif sk.startswith("EVENT#"):
                incident_data["timeline"].append(item)
            elif sk.startswith("COMMENT#"):
                incident_data["comments"].append(item)
            elif sk.startswith("USER#"):
                incident_data["participants"].append(item)
            elif sk.startswith("SUMMARY#"):
                incident_data["summaries"].append(item)
        
        if not incident_data["metadata"]:
            raise IncidentNotFoundError(f"Incident {incident_id} metadata not found")
        
        return incident_data