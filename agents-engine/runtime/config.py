"""
Configuration Management for AEGIS Ω Intelligence Engine.
Loads strongly-typed settings from environment variables and .env files.
"""

from functools import lru_cache
from typing import Optional
from pydantic import Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings backed by environment variables."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

    # -------------------------------------------------------------------------
    # Gemini & AI Model Configuration
    # NEVER hardcode GEMINI_API_KEY. It must be provided via environment or .env.
    # -------------------------------------------------------------------------
    gemini_api_key: Optional[SecretStr] = Field(
        default=None,
        validation_alias="GEMINI_API_KEY",
        description="Google Gemini API Key",
    )
    gemini_model: str = Field(
        default="gemini-2.0-flash",
        validation_alias="GEMINI_MODEL",
        description="Default Gemini model to use across agents",
    )

    # -------------------------------------------------------------------------
    # Runtime & Web Server Environment
    # -------------------------------------------------------------------------
    environment: str = Field(
        default="development",
        validation_alias="ENVIRONMENT",
        description="Runtime environment (development, staging, production)",
    )
    log_level: str = Field(
        default="INFO",
        validation_alias="LOG_LEVEL",
        description="Logging level",
    )
    debug: bool = Field(
        default=False,
        validation_alias="DEBUG",
        description="Enable debug mode",
    )
    port: int = Field(
        default=8080,
        validation_alias="PORT",
        description="HTTP port for Cloud Run service",
    )
    host: str = Field(
        default="0.0.0.0",
        validation_alias="HOST",
        description="HTTP host to bind for Cloud Run service",
    )

    # -------------------------------------------------------------------------
    # Google Cloud Platform (GCP) Configuration
    # -------------------------------------------------------------------------
    gcp_project_id: Optional[str] = Field(
        default=None,
        validation_alias="GCP_PROJECT_ID",
        description="Google Cloud Project ID",
    )
    gcp_region: str = Field(
        default="us-central1",
        validation_alias="GCP_REGION",
        description="Google Cloud default deployment region",
    )

    # Google Cloud Pub/Sub
    enable_gcp_pubsub: bool = Field(
        default=False,
        validation_alias="ENABLE_GCP_PUBSUB",
        description="Enable live Google Cloud Pub/Sub integration",
    )
    pubsub_topic_prefix: str = Field(
        default="",
        validation_alias="PUBSUB_TOPIC_PREFIX",
        description="Optional prefix for Pub/Sub topic names (e.g. staging_)",
    )
    pubsub_emulator_host: Optional[str] = Field(
        default=None,
        validation_alias="PUBSUB_EMULATOR_HOST",
        description="Local Pub/Sub emulator host for integration testing",
    )

    # Google Cloud SQL (PostgreSQL)
    enable_cloud_sql: bool = Field(
        default=False,
        validation_alias="ENABLE_CLOUD_SQL",
        description="Enable live Cloud SQL PostgreSQL persistence",
    )
    cloud_sql_connection_name: Optional[str] = Field(
        default=None,
        validation_alias="CLOUD_SQL_CONNECTION_NAME",
        description="Cloud SQL Instance Connection Name (project:region:instance)",
    )
    cloud_sql_database: str = Field(
        default="aegis_omega",
        validation_alias="CLOUD_SQL_DATABASE",
        description="Cloud SQL PostgreSQL database name",
    )
    cloud_sql_user: str = Field(
        default="aegis_app",
        validation_alias="CLOUD_SQL_USER",
        description="Cloud SQL PostgreSQL username",
    )
    cloud_sql_password: Optional[SecretStr] = Field(
        default=None,
        validation_alias="CLOUD_SQL_PASSWORD",
        description="Cloud SQL PostgreSQL password",
    )
    cloud_sql_host: Optional[str] = Field(
        default="127.0.0.1",
        validation_alias="CLOUD_SQL_HOST",
        description="PostgreSQL host (or /cloudsql/INSTANCE_CONNECTION_NAME for unix socket)",
    )
    cloud_sql_port: int = Field(
        default=5432,
        validation_alias="CLOUD_SQL_PORT",
        description="PostgreSQL port",
    )

    # Google Cloud Firestore
    enable_firestore: bool = Field(
        default=False,
        validation_alias="ENABLE_FIRESTORE",
        description="Enable live Google Cloud Firestore memory persistence",
    )
    firestore_database_id: str = Field(
        default="(default)",
        validation_alias="FIRESTORE_DATABASE_ID",
        description="Firestore database identifier",
    )

    # -------------------------------------------------------------------------
    # Event Bus Settings
    # -------------------------------------------------------------------------
    event_bus_max_queue_size: int = Field(
        default=10000,
        validation_alias="EVENT_BUS_MAX_QUEUE_SIZE",
        description="Maximum capacity of the in-memory event bus queue",
    )
    event_bus_enable_dead_letter_queue: bool = Field(
        default=True,
        validation_alias="EVENT_BUS_ENABLE_DEAD_LETTER_QUEUE",
        description="Enable dead-letter queue for failed event handlers",
    )

    # -------------------------------------------------------------------------
    # OpenTelemetry Observability
    # -------------------------------------------------------------------------
    otel_service_name: str = Field(
        default="aegis-omega-intelligence-engine",
        validation_alias="OTEL_SERVICE_NAME",
        description="OpenTelemetry service name",
    )
    otel_exporter_otlp_endpoint: str = Field(
        default="http://localhost:4317",
        validation_alias="OTEL_EXPORTER_OTLP_ENDPOINT",
        description="OTLP collector endpoint",
    )
    otel_traces_sampler: str = Field(
        default="always_on",
        validation_alias="OTEL_TRACES_SAMPLER",
        description="OpenTelemetry trace sampling strategy",
    )

    # -------------------------------------------------------------------------
    # Digital World (Member 1) API Configuration
    # -------------------------------------------------------------------------
    digital_world_api_base_url: str = Field(
        default="http://localhost:8080/api/v1",
        validation_alias="DIGITAL_WORLD_API_BASE_URL",
        description="Base URL for Member 1 Digital World REST API",
    )
    digital_world_ws_stream_url: str = Field(
        default="ws://localhost:8080/api/v1/events/stream",
        validation_alias="DIGITAL_WORLD_WS_STREAM_URL",
        description="WebSocket URL for Member 1 Digital World Live Event Stream",
    )
    digital_world_api_key: Optional[SecretStr] = Field(
        default=None,
        validation_alias="DIGITAL_WORLD_API_KEY",
        description="API Key to authenticate with Digital World services",
    )


@lru_cache()
def get_settings() -> Settings:
    """Get singleton cached application settings."""
    return Settings()
