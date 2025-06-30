"""Configuration management for Aegis Lambda functions."""

import os
from typing import Optional
from aws_lambda_powertools import Logger

logger = Logger()


class Config:
    """Configuration class for Lambda functions."""
    
    def __init__(self):
        """Initialize configuration from environment variables."""
        # Environment
        self.environment = self._get_env("ENVIRONMENT", "dev")
        self.region = self._get_env("AWS_REGION", "us-east-1")
        
        # DynamoDB
        self.table_name = self._get_env("TABLE_NAME")
        self.idempotency_table_name = self._get_env("IDEMPOTENCY_TABLE_NAME", "")
        
        # EventBridge
        self.event_bus_name = self._get_env("EVENT_BUS_NAME", "")
        
        # AppSync
        self.appsync_endpoint = self._get_env("APPSYNC_ENDPOINT", "")
        
        # Bedrock
        self.bedrock_model_id = self._get_env(
            "BEDROCK_MODEL_ID", 
            "anthropic.claude-3-sonnet-20240229-v1:0"
        )
        self.bedrock_max_tokens = int(self._get_env("MAX_TOKENS", "4000"))
        self.bedrock_temperature = float(self._get_env("TEMPERATURE", "0.7"))
        
        # Feature flags
        self.mock_external_services = self._get_env("MOCK_EXTERNAL_SERVICES", "false").lower() == "true"
        self.mock_ai_responses = self._get_env("MOCK_AI_RESPONSES", "false").lower() == "true"
        
        # Timeouts and limits
        self.default_timeout = int(self._get_env("DEFAULT_TIMEOUT_SECONDS", "300"))
        self.max_retries = int(self._get_env("MAX_RETRIES", "3"))
        
        # Log the configuration (excluding sensitive values)
        logger.info(
            "Configuration loaded",
            extra={
                "environment": self.environment,
                "region": self.region,
                "table_name": self.table_name,
                "mock_external_services": self.mock_external_services,
                "mock_ai_responses": self.mock_ai_responses
            }
        )
    
    def _get_env(self, key: str, default: Optional[str] = None) -> str:
        """Get environment variable with optional default."""
        value = os.environ.get(key, default)
        if value is None:
            raise ValueError(f"Required environment variable {key} is not set")
        return value
    
    @property
    def is_production(self) -> bool:
        """Check if running in production environment."""
        return self.environment == "prod"
    
    @property
    def is_local(self) -> bool:
        """Check if running in local environment."""
        return self.environment == "local"