"""
Deterministic Security Threat Detectors for AEGIS Ω Security Agent.
Pure Python heuristic and signature-based detectors.
If a strong detector fires, incident classification is forced to SECURITY_EVENT.
"""

import re
from typing import Any, Dict, List, Tuple
from pydantic import BaseModel, Field


class DetectorResult(BaseModel):
    """Result of running security threat detectors."""
    is_security_threat: bool
    fired_detectors: List[str] = Field(default_factory=list)
    threat_severity: str = "LOW"  # LOW, MEDIUM, HIGH, CRITICAL
    detected_signatures: List[str] = Field(default_factory=list)
    details: Dict[str, Any] = Field(default_factory=dict)


class SecurityThreatDetectors:
    """
    Suite of deterministic detectors checking for authentication attacks,
    exploit payloads, privilege escalations, and access anomalies.
    """

    # Suspicious payload signatures
    SQL_INJECTION_PATTERNS = [
        r"(?i)'\s*or\s+['\"]?1['\"]?\s*=\s*['\"]?1",
        r"(?i)union\s+select",
        r"(?i);\s*drop\s+table",
        r"(?i)--\s*$",
    ]
    COMMAND_INJECTION_PATTERNS = [
        r"(?i);\s*(rm\s+-rf|cat\s+/etc/passwd|shutdown|kill)",
        r"(?i)\|\s*(bash|sh|zsh|curl|wget)",
        r"(?i)&&\s*(nc\s+-e|curl\s+http|wget\s+http)",
    ]
    PATH_TRAVERSAL_PATTERNS = [
        r"\.\./\.\./",
        r"\.\.\\\.\.\\",
        r"/etc/shadow",
        r"/etc/passwd",
        r"c:\\windows\\system32\\config",
    ]

    @classmethod
    def detect_repeated_failed_logins(
        cls,
        metrics: Dict[str, Any],
        events: List[Dict[str, Any]],
    ) -> Tuple[bool, List[str]]:
        """Detect brute-force or credential stuffing login failures."""
        findings = []

        # Check metrics
        failed_ssh = float(metrics.get("failed_ssh_attempts_1m", 0))
        if failed_ssh >= 10:
            findings.append(f"Brute-force SSH attack: {failed_ssh} failed attempts/min")

        failed_auth_pct = float(metrics.get("failed_auth_rate_pct", 0))
        if failed_auth_pct >= 80.0:
            findings.append(f"Excessive authentication failure rate: {failed_auth_pct}%")

        db_auth_errs = float(metrics.get("db_connection_errors", 0))
        if db_auth_errs >= 1000:
            findings.append(f"High volume auth connection errors: {db_auth_errs}")

        # Check event stream
        login_fail_count = sum(1 for e in events if e.get("event_type") == "LOGIN_FAILURE")
        if login_fail_count >= 3:
            findings.append(f"Repeated LOGIN_FAILURE events in cluster: count={login_fail_count}")

        return len(findings) > 0, findings

    @classmethod
    def detect_suspicious_payloads(
        cls,
        text_samples: List[str],
    ) -> Tuple[bool, List[str]]:
        """Scan logs, payloads, and strings for exploit signatures (SQLi, RCE, Traversal)."""
        findings = []
        for text in text_samples:
            for pattern in cls.SQL_INJECTION_PATTERNS:
                if re.search(pattern, text):
                    findings.append(f"SQL Injection signature detected: '{pattern}'")

            for pattern in cls.COMMAND_INJECTION_PATTERNS:
                if re.search(pattern, text):
                    findings.append(f"Remote Command Injection signature detected: '{pattern}'")

            for pattern in cls.PATH_TRAVERSAL_PATTERNS:
                if re.search(pattern, text):
                    findings.append(f"Path Traversal signature detected: '{pattern}'")

        return len(findings) > 0, findings

    @classmethod
    def detect_privilege_escalation(
        cls,
        metrics: Dict[str, Any],
        events: List[Dict[str, Any]],
        text_samples: List[str],
    ) -> Tuple[bool, List[str]]:
        """Detect unauthorized privilege escalation or known CVE exploit execution."""
        findings = []

        # Check CVE identifiers in metrics
        cve = metrics.get("cve_identifier")
        if cve:
            findings.append(f"Explicit CVE threat vector identified: {cve}")

        mitre = metrics.get("mitre_technique")
        if mitre:
            findings.append(f"MITRE ATT&CK technique active: {mitre}")

        # Check text signatures
        for text in text_samples:
            if re.search(r"(?i)(sudo\s+su|su\s+root|chmod\s+777|setuid|cve-\d{4}-\d+)", text):
                findings.append(f"Privilege escalation syntax observed in log: '{text[:80]}'")

        return len(findings) > 0, findings

    @classmethod
    def detect_abnormal_access(
        cls,
        metrics: Dict[str, Any],
    ) -> Tuple[bool, List[str]]:
        """Detect IP reputation hazards or anomalous geographic origin."""
        findings = []
        ip_rep = float(metrics.get("source_ip_reputation_score", 0.0))
        if ip_rep >= 0.75:
            findings.append(f"High-risk source IP reputation score: {ip_rep} >= 0.75 threshold")

        return len(findings) > 0, findings

    @classmethod
    def evaluate_all_detectors(
        cls,
        metrics: Dict[str, Any],
        events: List[Dict[str, Any]],
        text_samples: List[str],
        prompt_injections: List[str],
    ) -> DetectorResult:
        """Run all deterministic detectors and synthesize threat assessment."""
        fired = []
        signatures = []

        # 1. Prompt Injections detected by sanitizer
        if prompt_injections:
            fired.append("PROMPT_INJECTION_ATTACK")
            for p in prompt_injections:
                signatures.append(f"Prompt Injection Pattern: {p}")

        # 2. Failed logins
        is_login_threat, login_reasons = cls.detect_repeated_failed_logins(metrics, events)
        if is_login_threat:
            fired.append("REPEATED_FAILED_LOGINS")
            signatures.extend(login_reasons)

        # 3. Payload signatures
        is_payload_threat, payload_reasons = cls.detect_suspicious_payloads(text_samples)
        if is_payload_threat:
            fired.append("SUSPICIOUS_PAYLOAD_SIGNATURES")
            signatures.extend(payload_reasons)

        # 4. Privilege escalation
        is_priv_threat, priv_reasons = cls.detect_privilege_escalation(metrics, events, text_samples)
        if is_priv_threat:
            fired.append("PRIVILEGE_ESCALATION_ATTEMPT")
            signatures.extend(priv_reasons)

        # 5. Abnormal access
        is_access_threat, access_reasons = cls.detect_abnormal_access(metrics)
        if is_access_threat:
            fired.append("ABNORMAL_ACCESS_ANOMALY")
            signatures.extend(access_reasons)

        is_threat = len(fired) > 0
        severity = "CRITICAL" if len(fired) >= 2 or "PROMPT_INJECTION_ATTACK" in fired else ("HIGH" if is_threat else "LOW")

        return DetectorResult(
            is_security_threat=is_threat,
            fired_detectors=fired,
            threat_severity=severity,
            detected_signatures=signatures,
            details={
                "metrics_scanned": len(metrics),
                "events_scanned": len(events),
                "text_samples_scanned": len(text_samples),
            },
        )
