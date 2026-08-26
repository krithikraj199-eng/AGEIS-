"""
Security Classification Models and Schema Definitions for AEGIS Ω.
"""

from enum import Enum
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


class IncidentClassification(str, Enum):
    """Allowed classification categories for Security Agent."""
    OPERATIONAL_FAILURE = "OPERATIONAL_FAILURE"
    CONFIGURATION_ERROR = "CONFIGURATION_ERROR"
    HUMAN_ERROR = "HUMAN_ERROR"
    SECURITY_EVENT = "SECURITY_EVENT"
    UNKNOWN = "UNKNOWN"


class SecurityOutput(BaseModel):
    """
    Required output schema for Security Agent:
    { classification, risk_flag, detected_patterns, rationale }
    """
    incident_id: str
    correlation_id: str
    asset_id: str
    classification: IncidentClassification = Field(
        description="Incident category: OPERATIONAL_FAILURE, CONFIGURATION_ERROR, HUMAN_ERROR, SECURITY_EVENT, UNKNOWN",
    )
    risk_flag: bool = Field(
        description="True if security threat or active exploit detected",
    )
    detected_patterns: List[str] = Field(
        default_factory=list,
        description="List of detected malicious patterns, injection signatures, or threat vectors",
    )
    rationale: str = Field(
        description="Justification and explanation of the security classification decision",
    )
    threat_level: str = Field(
        default="LOW",
        description="Assessed threat level: LOW, MEDIUM, HIGH, CRITICAL",
    )
    is_security_incident: bool = Field(
        default=False,
        description="True if classified as SECURITY_EVENT",
    )
    cve_references: List[str] = Field(
        default_factory=list,
        description="Identified CVE references",
    )
    compliance_status: str = Field(
        default="COMPLIANT",
        description="Regulatory / audit compliance state",
    )
    security_clearance: bool = Field(
        default=True,
        description="True if safe to proceed with automated remediation",
    )
    screened_at: str
