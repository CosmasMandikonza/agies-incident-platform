"""
Triage Function Lambda
Performs automated incident triage and classification based on rules and patterns.
"""

import json
import re
from typing import Dict, Any, List, Optional, Tuple
from datetime import datetime
from aws_lambda_powertools import Logger, Tracer, Metrics
from aws_lambda_powertools.metrics import MetricUnit
from aws_lambda_powertools.utilities.typing import LambdaContext

# Import shared modules
from shared.config import Config
from shared.models import Incident, TimelineEvent
from shared.dynamodb_client import DynamoDBClient
from shared.event_publisher import EventPublisher
from aegis_shared.constants import (
    EVENT_SOURCE_INCIDENTS,
    EVENT_TYPE_TIMELINE_EVENT_ADDED,
    SEVERITY_P0,
    SEVERITY_P1,
    SEVERITY_P2,
    SEVERITY_P3,
    SEVERITY_P4
)
from aegis_shared.exceptions import IncidentNotFoundError

# Initialize AWS Lambda Powertools
logger = Logger()
tracer = Tracer()
metrics = Metrics()

# Initialize configuration
config = Config()

# Initialize clients
dynamodb_client = DynamoDBClient(config.table_name)
event_publisher = EventPublisher(config.event_bus_name)


class TriageEngine:
    """Engine for automated incident triage."""
    
    def __init__(self):
        """Initialize triage engine with rules."""
        self.severity_rules = self._load_severity_rules()
        self.escalation_rules = self._load_escalation_rules()
        self.auto_remediation_rules = self._load_auto_remediation_rules()
    
    def _load_severity_rules(self) -> List[Dict[str, Any]]:
        """Load severity classification rules."""
        return [
            # P0 - Critical rules
            {
                "severity": SEVERITY_P0,
                "patterns": [
                    r"production.*down",
                    r"complete.*outage",
                    r"security.*breach",
                    r"data.*loss",
                    r"critical.*failure"
                ],
                "keywords": ["critical", "emergency", "outage", "breach"],
                "services": ["payment", "authentication", "database-master"],
                "error_rate_threshold": 50.0,  # > 50% error rate
                "response_time_threshold": 10000  # > 10 seconds
            },
            # P1 - High severity rules
            {
                "severity": SEVERITY_P1,
                "patterns": [
                    r"partial.*outage",
                    r"degraded.*performance",
                    r"high.*error.*rate",
                    r"memory.*leak"
                ],
                "keywords": ["high", "severe", "degraded", "unstable"],
                "services": ["api-gateway", "core-service", "database-replica"],
                "error_rate_threshold": 20.0,  # > 20% error rate
                "response_time_threshold": 5000  # > 5 seconds
            },
            # P2 - Medium severity rules
            {
                "severity": SEVERITY_P2,
                "patterns": [
                    r"elevated.*errors",
                    r"performance.*issue",
                    r"intermittent.*failure"
                ],
                "keywords": ["medium", "moderate", "intermittent", "occasional"],
                "services": ["batch-processor", "analytics", "reporting"],
                "error_rate_threshold": 10.0,  # > 10% error rate
                "response_time_threshold": 2000  # > 2 seconds
            },
            # P3 - Low severity rules
            {
                "severity": SEVERITY_P3,
                "patterns": [
                    r"minor.*issue",
                    r"cosmetic.*bug",
                    r"non-critical"
                ],
                "keywords": ["low", "minor", "cosmetic", "ui"],
                "services": ["frontend", "docs", "staging"],
                "error_rate_threshold": 5.0,  # > 5% error rate
                "response_time_threshold": 1000  # > 1 second
            }
        ]
    
    def _load_escalation_rules(self) -> List[Dict[str, Any]]:
        """Load escalation rules."""
        return [
            {
                "condition": "unacknowledged_p0",
                "threshold_minutes": 5,
                "action": "page_on_call_lead"
            },
            {
                "condition": "unacknowledged_p1",
                "threshold_minutes": 15,
                "action": "page_secondary_on_call"
            },
            {
                "condition": "long_running_incident",
                "threshold_minutes": 60,
                "action": "notify_management"
            },
            {
                "condition": "multiple_related_incidents",
                "threshold_count": 3,
                "action": "create_major_incident"
            }
        ]
    
    def _load_auto_remediation_rules(self) -> List[Dict[str, Any]]:
        """Load auto-remediation rules."""
        return [
            {
                "pattern": r"lambda.*concurrent.*execution.*limit",
                "action": "increase_lambda_concurrency",
                "parameters": {"increase_by": 100}
            },
            {
                "pattern": r"dynamodb.*throttled",
                "action": "increase_dynamodb_capacity",
                "parameters": {"increase_percent": 50}
            },
            {
                "pattern": r"disk.*space.*full",
                "action": "cleanup_old_logs",
                "parameters": {"days_to_keep": 7}
            },
            {
                "pattern": r"memory.*exhausted",
                "action": "restart_service",
                "parameters": {"wait_seconds": 30}
            }
        ]
    
    @tracer.capture_method
    def triage_incident(self, incident: Incident) -> Dict[str, Any]:
        """Perform automated triage on an incident."""
        triage_result = {
            "incident_id": incident.id,
            "original_severity": incident.severity,
            "recommended_severity": incident.severity,
            "confidence_score": 0.0,
            "matched_rules": [],
            "recommended_actions": [],
            "auto_remediation": None,
            "related_incidents": []
        }
        
        # Analyze incident details
        analysis_text = f"{incident.title} {incident.description or ''}".lower()
        
        # Check severity rules
        severity_recommendation = self._analyze_severity(
            analysis_text, 
            incident.metadata
        )
        
        if severity_recommendation:
            triage_result["recommended_severity"] = severity_recommendation["severity"]
            triage_result["confidence_score"] = severity_recommendation["confidence"]
            triage_result["matched_rules"] = severity_recommendation["matched_rules"]
        
        # Check for auto-remediation opportunities
        auto_remediation = self._check_auto_remediation(analysis_text)
        if auto_remediation:
            triage_result["auto_remediation"] = auto_remediation
        
        # Find related incidents
        related = self._find_related_incidents(incident)
        triage_result["related_incidents"] = related
        
        # Generate recommended actions
        triage_result["recommended_actions"] = self._generate_recommendations(
            incident,
            triage_result
        )
        
        logger.info("Incident triage completed", extra={
            "incident_id": incident.id,
            "recommended_severity": triage_result["recommended_severity"],
            "confidence": triage_result["confidence_score"]
        })
        
        return triage_result
    
    @tracer.capture_method
    def _analyze_severity(self, text: str, metadata: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Analyze text and metadata to recommend severity."""
        best_match = None
        highest_confidence = 0.0
        
        for rule in self.severity_rules:
            confidence = 0.0
            matched_criteria = []
            
            # Check patterns
            for pattern in rule["patterns"]:
                if re.search(pattern, text):
                    confidence += 0.3
                    matched_criteria.append(f"pattern: {pattern}")
            
            # Check keywords
            keyword_matches = sum(1 for keyword in rule["keywords"] if keyword in text)
            if keyword_matches > 0:
                confidence += 0.2 * (keyword_matches / len(rule["keywords"]))
                matched_criteria.append(f"keywords: {keyword_matches}/{len(rule['keywords'])}")
            
            # Check service impact
            if metadata.get("service") in rule["services"]:
                confidence += 0.3
                matched_criteria.append(f"service: {metadata.get('service')}")
            
            # Check metrics thresholds
            if metadata.get("error_rate", 0) > rule["error_rate_threshold"]:
                confidence += 0.2
                matched_criteria.append(f"error_rate: {metadata.get('error_rate')}%")
            
            if metadata.get("response_time", 0) > rule["response_time_threshold"]:
                confidence += 0.2
                matched_criteria.append(f"response_time: {metadata.get('response_time')}ms")
            
            # Update best match
            if confidence > highest_confidence:
                highest_confidence = confidence
                best_match = {
                    "severity": rule["severity"],
                    "confidence": min(confidence, 1.0),  # Cap at 100%
                    "matched_rules": matched_criteria
                }
        
        return best_match
    
    @tracer.capture_method
    def _check_auto_remediation(self, text: str) -> Optional[Dict[str, Any]]:
        """Check if auto-remediation is possible."""
        for rule in self.auto_remediation_rules:
            if re.search(rule["pattern"], text):
                return {
                    "action": rule["action"],
                    "parameters": rule["parameters"],
                    "pattern_matched": rule["pattern"]
                }
        return None
    
    @tracer.capture_method
    def _find_related_incidents(self, incident: Incident) -> List[Dict[str, Any]]:
        """Find incidents that might be related."""
        related = []
        
        try:
            # Query for recent open incidents
            recent_incidents, _ = dynamodb_client.query_gsi(
                index_name="GSI1",
                pk_value="STATUS#OPEN",
                limit=20
            )
            
            for item in recent_incidents:
                if item["id"] == incident.id:
                    continue  # Skip self
                
                # Calculate similarity score
                similarity = self._calculate_similarity(incident, item)
                
                if similarity > 0.5:  # Threshold for considering related
                    related.append({
                        "incident_id": item["id"],
                        "title": item["title"],
                        "similarity_score": similarity
                    })
            
            # Sort by similarity score
            related.sort(key=lambda x: x["similarity_score"], reverse=True)
            
        except Exception as e:
            logger.error(f"Failed to find related incidents: {str(e)}")
        
        return related[:5]  # Return top 5 related incidents
    
    def _calculate_similarity(self, incident1: Incident, incident2: Dict[str, Any]) -> float:
        """Calculate similarity score between two incidents."""
        score = 0.0
        
        # Compare titles
        title1_words = set(incident1.title.lower().split())
        title2_words = set(incident2["title"].lower().split())
        title_overlap = len(title1_words & title2_words) / max(len(title1_words), len(title2_words))
        score += title_overlap * 0.4
        
        # Compare severity
        if incident1.severity == incident2.get("severity"):
            score += 0.2
        
        # Compare source
        if incident1.source == incident2.get("source"):
            score += 0.2
        
        # Compare service (if available)
        if (incident1.metadata.get("service") and 
            incident1.metadata.get("service") == incident2.get("metadata", {}).get("service")):
            score += 0.2
        
        return score
    
    def _generate_recommendations(self, incident: Incident, 
                                 triage_result: Dict[str, Any]) -> List[str]:
        """Generate recommended actions based on triage."""
        recommendations = []
        
        # Severity adjustment recommendation
        if triage_result["recommended_severity"] != incident.severity:
            recommendations.append(
                f"Consider updating severity from {incident.severity} to "
                f"{triage_result['recommended_severity']} "
                f"(confidence: {triage_result['confidence_score']:.0%})"
            )
        
        # Auto-remediation recommendation
        if triage_result["auto_remediation"]:
            recommendations.append(
                f"Auto-remediation available: {triage_result['auto_remediation']['action']}"
            )
        
        # Related incidents recommendation
        if triage_result["related_incidents"]:
            recommendations.append(
                f"Found {len(triage_result['related_incidents'])} potentially related incidents. "
                "Consider investigating for common root cause."
            )
        
        # Severity-based recommendations
        if triage_result["recommended_severity"] in [SEVERITY_P0, SEVERITY_P1]:
            recommendations.extend([
                "Page on-call engineer immediately",
                "Create war room channel",
                "Prepare customer communication"
            ])
        elif triage_result["recommended_severity"] == SEVERITY_P2:
            recommendations.extend([
                "Notify on-call engineer via Slack",
                "Monitor for escalation"
            ])
        
        return recommendations


# Initialize triage engine
triage_engine = TriageEngine()


@tracer.capture_method
def create_triage_timeline_event(incident_id: str, triage_result: Dict[str, Any]) -> None:
    """Create timeline event for triage results."""
    # Build description
    description_parts = [
        f"Automated triage completed. Recommended severity: {triage_result['recommended_severity']}"
    ]
    
    if triage_result["confidence_score"] > 0:
        description_parts.append(f"Confidence: {triage_result['confidence_score']:.0%}")
    
    if triage_result["related_incidents"]:
        description_parts.append(
            f"Found {len(triage_result['related_incidents'])} related incidents"
        )
    
    # Create timeline event
    timeline_event = TimelineEvent(
        incident_id=incident_id,
        event_id=f"triage-{datetime.utcnow().timestamp()}",
        type="AUTOMATED_TRIAGE",
        description=". ".join(description_parts),
        source="Triage Engine",
        metadata=triage_result
    )
    
    # Save to DynamoDB
    dynamodb_client.put_item(timeline_event.to_dynamodb_item())
    
    # Publish event
    event_publisher.publish_incident_event(
        incident_id=incident_id,
        detail_type=EVENT_TYPE_TIMELINE_EVENT_ADDED,
        additional_detail={
            "eventType": "AUTOMATED_TRIAGE",
            "eventId": timeline_event.event_id
        }
    )


@logger.inject_lambda_context
@tracer.capture_lambda_handler
@metrics.log_metrics(capture_cold_start_metric=True)
def handler(event: Dict[str, Any], context: LambdaContext) -> Dict[str, Any]:
    """
    Lambda handler for incident triage.
    Called by Step Functions workflow.
    """
    try:
        logger.info("Triage function invoked", extra={"event": event})
        
        # Extract incident ID from event
        incident_id = event.get("incidentId")
        if not incident_id:
            raise ValueError("Missing incidentId in event")
        
        # Get incident data
        incident_data = dynamodb_client.get_incident(incident_id)
        metadata = incident_data["metadata"]
        
        # Create incident model
        incident = Incident(
            id=incident_id,
            title=metadata["title"],
            description=metadata.get("description"),
            severity=metadata["severity"],
            source=metadata["source"],
            status=metadata["status"],
            created_at=datetime.fromisoformat(metadata["created_at"]),
            metadata=metadata.get("metadata", {})
        )
        
        # Perform triage
        triage_result = triage_engine.triage_incident(incident)
        
        # Create timeline event
        create_triage_timeline_event(incident_id, triage_result)
        
        # Update incident if severity changed
        if (triage_result["recommended_severity"] != incident.severity and 
            triage_result["confidence_score"] > 0.7):  # Only update if high confidence
            
            logger.info(f"Updating incident severity based on triage", extra={
                "incident_id": incident_id,
                "old_severity": incident.severity,
                "new_severity": triage_result["recommended_severity"]
            })
            
            dynamodb_client.update_item(
                pk=f"INCIDENT#{incident_id}",
                sk="METADATA",
                updates={
                    "severity": triage_result["recommended_severity"],
                    "updated_at": datetime.utcnow().isoformat()
                }
            )
            
            # Emit metric
            metrics.add_metric(name="SeverityAutoUpdated", unit=MetricUnit.Count, value=1)
        
        # Emit triage metrics
        metrics.add_metric(name="IncidentTriaged", unit=MetricUnit.Count, value=1)
        metrics.add_metadata(key="severity", value=triage_result["recommended_severity"])
        metrics.add_metadata(key="confidence", value=f"{triage_result['confidence_score']:.2f}")
        
        # Return triage result for Step Functions
        return {
            "incidentId": incident_id,
            "severity": triage_result["recommended_severity"],
            "originalSeverity": incident.severity,
            "confidence": triage_result["confidence_score"],
            "relatedIncidents": len(triage_result["related_incidents"]),
            "autoRemediation": triage_result["auto_remediation"] is not None,
            "recommendations": triage_result["recommended_actions"]
        }
        
    except IncidentNotFoundError as e:
        logger.error(f"Incident not found: {str(e)}")
        raise
    except Exception as e:
        logger.error(f"Triage failed: {str(e)}", exc_info=True)
        metrics.add_metric(name="TriageError", unit=MetricUnit.Count, value=1)
        raise