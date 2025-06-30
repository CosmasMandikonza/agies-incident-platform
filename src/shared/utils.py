"""Shared utility functions."""
import json
import uuid

def create_response(status_code: int, body: dict) -> dict:
    """Creates a standard API Gateway response."""
    return {
        "statusCode": status_code,
        "headers": {
            "Content-Type": "application/json",
            "Access-Control-Allow-Origin": "*",
        },
        "body": json.dumps(body)
    }

def generate_id(prefix: str) -> str:
    """Generates a unique, prefixed ID."""
    return f"{prefix.upper()}-{uuid.uuid4()}"