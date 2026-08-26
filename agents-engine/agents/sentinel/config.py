"""
Configuration and Threshold Definitions for Sentinel Agent.
All thresholds are fully configurable and never hardcoded in the detection logic.
"""

from pydantic import BaseModel, Field


class SentinelThresholds(BaseModel):
    """
    Configurable threshold parameters for deterministic anomaly detection.
    """
    cpu_threshold_pct: float = Field(
        default=90.0,
        description="CPU utilization percentage triggering threshold breach",
    )
    memory_threshold_pct: float = Field(
        default=95.0,
        description="Memory usage percentage triggering threshold breach",
    )
    disk_threshold_pct: float = Field(
        default=95.0,
        description="Disk utilization percentage triggering threshold breach",
    )
    latency_threshold_ms: float = Field(
        default=2000.0,
        description="Latency threshold in milliseconds (p99 or query latency)",
    )
    error_rate_threshold_pct: float = Field(
        default=50.0,
        description="Error rate percentage (HTTP 5xx or failed auth) triggering threshold breach",
    )
    correlation_window_seconds: float = Field(
        default=60.0,
        description="Time window in seconds to aggregate related events by correlation_id",
    )
    min_events_for_gemini: int = Field(
        default=2,
        description="Minimum number of correlated anomalous events required before invoking Gemini",
    )
