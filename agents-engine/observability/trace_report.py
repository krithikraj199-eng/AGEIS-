"""
OpenTelemetry Incident Trace Report CLI for AEGIS Ω.
Generates an audit-grade chronological timeline from recorded OpenTelemetry span data.

Usage:
    python observability/trace_report.py <incident_id>
    python observability/trace_report.py --list
"""

import argparse
import os
import sys
from datetime import datetime
from pathlib import Path
from typing import List, Optional

# Ensure project root is on sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

# Reconfigure stdout for UTF-8 compatibility on Windows terminals
if hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass

from observability.trace_store import SpanRecord, trace_store


def format_timestamp(ts_str: str) -> str:
    """Format ISO timestamp into HH:MM:SS."""
    try:
        dt = datetime.fromisoformat(ts_str.replace("Z", "+00:00"))
        return dt.strftime("%H:%M:%S")
    except Exception:
        return ts_str[:8]


def generate_trace_timeline(spans: List[SpanRecord], incident_id: str) -> str:
    """
    Generate chronological text report from real recorded span data.
    Strictly zero hardcoding.
    """
    if not spans:
        return f"No trace data found for incident: {incident_id}"

    lines = []
    lines.append("=" * 80)
    lines.append(f"  AEGIS OMEGA Incident Trace Report: {incident_id}")
    lines.append("=" * 80)
    lines.append(f"{'Timestamp':<10} {'Agent / Stage':<16} {'Status':<10} {'Summary / Event'}")
    lines.append("-" * 80)

    for span in spans:
        t_str = span.time_formatted or format_timestamp(span.timestamp)
        agent = span.agent_id or span.span_name.replace("agent.", "").capitalize()
        status = span.status
        summary = span.summary or f"{agent} processed event"
        lines.append(f"{t_str:<10} {agent:<16} {status:<10} {summary}")

    lines.append("=" * 80)
    lines.append(f"Total Spans Recorded: {len(spans)}")
    lines.append("=" * 80)
    return "\n".join(lines)


def generate_simple_timeline(spans: List[SpanRecord]) -> str:
    """
    Generate concise chronological timeline requested in specification:
    19:42:01 Sentinel detected anomaly
    19:42:02 Investigator started
    ...
    19:42:15 Verifier SUCCESS
    """
    lines = []
    for span in spans:
        t_str = span.time_formatted or format_timestamp(span.timestamp)
        agent = span.agent_id or span.span_name.replace("agent.", "").capitalize()
        summary = span.summary or f"{agent} {span.status}"
        lines.append(f"{t_str} {summary}")
    return "\n".join(lines)


def main():
    parser = argparse.ArgumentParser(
        description="AEGIS Ω — OpenTelemetry Incident Trace Timeline Reporter",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "incident_id",
        nargs="?",
        help="Incident identifier to generate trace report for (e.g. INC-cascade-DATABASE-01-178767)",
    )
    parser.add_argument(
        "--list",
        action="store_true",
        help="List all incident IDs with recorded trace data",
    )
    parser.add_argument(
        "--format",
        choices=["table", "simple"],
        default="table",
        help="Output format: table (default) or simple",
    )

    args = parser.parse_args()

    if args.list or not args.incident_id:
        incident_ids = trace_store.get_all_incident_ids()
        if not incident_ids:
            print("No recorded incident traces found in trace store.")
            sys.exit(0)
        print("Recorded Incident Traces:")
        for inc_id in incident_ids:
            spans = trace_store.get_trace(inc_id)
            print(f" - {inc_id} ({len(spans)} spans)")
        sys.exit(0)

    spans = trace_store.get_trace(args.incident_id)
    if not spans:
        # Check partial substring match if full ID not exact
        all_ids = trace_store.get_all_incident_ids()
        matched = [i for i in all_ids if args.incident_id in i]
        if matched:
            spans = trace_store.get_trace(matched[0])
            args.incident_id = matched[0]

    if not spans:
        print(f"Error: No recorded trace spans found for incident '{args.incident_id}'.")
        print("Available incident IDs:")
        for inc_id in trace_store.get_all_incident_ids():
            print(f"  * {inc_id}")
        sys.exit(1)

    if args.format == "simple":
        print(generate_simple_timeline(spans))
    else:
        print(generate_trace_timeline(spans, args.incident_id))


if __name__ == "__main__":
    main()
