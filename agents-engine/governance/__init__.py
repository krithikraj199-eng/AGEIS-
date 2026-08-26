"""
Governance Package for AEGIS Ω.
Provides Agent Registry, Scoped Identity & Permissions, Security Sanitization, Shared Guardrails, and Agent Gateway.
"""

from .identity import AgentPermission, DEFAULT_AGENT_PERMISSIONS, AgentIdentity
from .registry import AgentRecord, AgentRegistry
from .gateway import (
    AgentGateway,
    SlidingWindowRateLimiter,
    GovernanceSecurityError,
    PermissionDeniedError,
    RateLimitExceededError,
)
from .sanitizer import LogSanitizer, SanitizedLogResult

# Alias for backwards compatibility
SanitizationResult = SanitizedLogResult

from .guardrails import (
    GuardrailSanitizationResult,
    OutputValidationResult,
    SharedGuardrailEngine,
    sanitize_untrusted_content,
    sanitize_untrusted_input,
    wrap_prompt_with_data_guardrails,
    validate_agent_output,
)

__all__ = [
    "AgentPermission",
    "DEFAULT_AGENT_PERMISSIONS",
    "AgentIdentity",
    "AgentRecord",
    "AgentRegistry",
    "AgentGateway",
    "SlidingWindowRateLimiter",
    "GovernanceSecurityError",
    "PermissionDeniedError",
    "RateLimitExceededError",
    "LogSanitizer",
    "SanitizedLogResult",
    "SanitizationResult",
    "GuardrailSanitizationResult",
    "OutputValidationResult",
    "SharedGuardrailEngine",
    "sanitize_untrusted_content",
    "sanitize_untrusted_input",
    "wrap_prompt_with_data_guardrails",
    "validate_agent_output",
]
