"""Authenticated in-process agent gateway with validation and prompt-injection guards."""

from __future__ import annotations

import re
from collections import defaultdict, deque
from datetime import datetime, timezone
from typing import Any, Dict

from ..governance.registry import AgentRegistry, AuditLog


INJECTION_PATTERNS = (
    re.compile(r"ignore\s+(all\s+)?previous\s+instructions", re.I),
    re.compile(r"reveal\s+(the\s+)?(system\s+)?prompt", re.I),
    re.compile(r"execute\s+(this\s+)?(shell|command)", re.I),
    re.compile(r"disable\s+(security|guardrails|policy)", re.I),
)


class AgentGateway:
    def __init__(self, registry: AgentRegistry, audit: AuditLog, rate_limit: int = 120) -> None:
        self.registry = registry
        self.audit = audit
        self.rate_limit = rate_limit
        self._traffic: Dict[str, deque[float]] = defaultdict(deque)

    def dispatch(
        self,
        *,
        sender: str,
        recipient: str,
        action: str,
        payload: Dict[str, Any],
        incident_id: str | None = None,
    ) -> Dict[str, Any]:
        if recipient not in {entry["agent_id"] for entry in self.registry.list()}:
            raise PermissionError(f"Unknown recipient agent: {recipient}")
        if sender != "system" and sender not in {entry["agent_id"] for entry in self.registry.list()}:
            raise PermissionError(f"Unknown sender agent: {sender}")
        self._check_rate(sender)
        sanitized, blocked = self._sanitize(payload)
        envelope = {
            "sender": sender,
            "recipient": recipient,
            "action": action,
            "incident_id": incident_id,
            "payload": sanitized,
            "blocked_fragments": blocked,
            "validated": True,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
        self.audit.append(
            "gateway", "message_routed", incident_id=incident_id,
            resource=f"{sender}->{recipient}", details={"action": action, "blocked_fragments": blocked},
        )
        return envelope

    def _check_rate(self, sender: str) -> None:
        now = datetime.now(timezone.utc).timestamp()
        traffic = self._traffic[sender]
        while traffic and now - traffic[0] > 60:
            traffic.popleft()
        if len(traffic) >= self.rate_limit:
            raise RuntimeError(f"Gateway rate limit exceeded for {sender}")
        traffic.append(now)

    def _sanitize(self, value: Any) -> tuple[Any, int]:
        blocked = 0
        if isinstance(value, str):
            clean = value[:8000]
            for pattern in INJECTION_PATTERNS:
                clean, count = pattern.subn("[BLOCKED_UNTRUSTED_INSTRUCTION]", clean)
                blocked += count
            return clean, blocked
        if isinstance(value, dict):
            result = {}
            for key, item in list(value.items())[:100]:
                cleaned, count = self._sanitize(item)
                result[str(key)[:120]] = cleaned
                blocked += count
            return result, blocked
        if isinstance(value, list):
            result = []
            for item in value[:200]:
                cleaned, count = self._sanitize(item)
                result.append(cleaned)
                blocked += count
            return result, blocked
        return value, blocked

