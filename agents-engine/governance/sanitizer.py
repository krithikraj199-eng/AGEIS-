"""
Reusable Log & Prompt Sanitizer for AEGIS Ω.
Protects AI agents against prompt injection and malicious instruction execution in logs.
"""

import html
import re
from typing import List, Tuple
from pydantic import BaseModel, Field


class SanitizedLogResult(BaseModel):
    """Result of sanitizing untrusted log data."""
    original_text: str
    sanitized_text: str
    detected_injection_patterns: List[str] = Field(default_factory=list)
    has_injection_risk: bool = False
    wrapped_data_block: str


class LogSanitizer:
    """
    Sanitizes external untrusted logs and telemetry text before it reaches Gemini.
    Neutralizes prompt injection patterns and encapsulates text within strict XML boundary tags.
    """

    # Signatures commonly used in prompt injection attacks
    INJECTION_PATTERNS: List[Tuple[str, str]] = [
        (r"(?i)ignore\s+(all\s+)?previous\s+instructions", "IGNORE_PREVIOUS_INSTRUCTIONS"),
        (r"(?i)disregard\s+(all\s+)?prior\s+instructions", "DISREGARD_PRIOR_INSTRUCTIONS"),
        (r"(?i)system\s*:", "SYSTEM_PROMPT_INJECTION"),
        (r"(?i)developer\s*:", "DEVELOPER_PROMPT_INJECTION"),
        (r"(?i)you\s+are\s+now", "ROLEPLAY_PROMPT_INJECTION"),
        (r"(?i)follow\s+these\s+instructions", "FOLLOW_INSTRUCTIONS_OVERRIDE"),
        (r"(?i)override\s+system\s+prompt", "SYSTEM_OVERRIDE_ATTEMPT"),
        (r"(?i)mark\s+this\s+incident\s+as\s+safe", "SAFETY_CLASSIFICATION_TAMPERING"),
        (r"(?i)output\s+the\s+following\s+json", "STRUCTURED_OUTPUT_HIJACK"),
    ]

    @classmethod
    def sanitize(cls, raw_text: str) -> SanitizedLogResult:
        """
        Scan and sanitize untrusted text:
        1. Detect and record injection patterns.
        2. Neutralize injection triggers.
        3. Escape XML tag delimiters.
        4. Wrap in <untrusted_log_data> boundary container.
        """
        if not raw_text:
            return SanitizedLogResult(
                original_text="",
                sanitized_text="",
                detected_injection_patterns=[],
                has_injection_risk=False,
                wrapped_data_block="<untrusted_log_data>\n</untrusted_log_data>",
            )

        detected = []
        sanitized = raw_text

        # 1. Detect injection patterns
        for pattern, label in cls.INJECTION_PATTERNS:
            matches = re.findall(pattern, raw_text)
            if matches:
                detected.append(label)
                # Defuse the injection text
                sanitized = re.sub(
                    pattern,
                    lambda m: f"[DEFUSED_INJECTION_ATTEMPT: {label}]",
                    sanitized,
                )

        # 2. Prevent XML boundary breakout (escape any stray closing tags)
        sanitized = sanitized.replace("</untrusted_log_data>", "&lt;/untrusted_log_data&gt;")
        sanitized = sanitized.replace("<untrusted_log_data>", "&lt;untrusted_log_data&gt;")

        has_risk = len(detected) > 0
        wrapped = f"<untrusted_log_data>\n{sanitized}\n</untrusted_log_data>"

        return SanitizedLogResult(
            original_text=raw_text,
            sanitized_text=sanitized,
            detected_injection_patterns=detected,
            has_injection_risk=has_risk,
            wrapped_data_block=wrapped,
        )
