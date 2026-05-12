"""Dispatch records, acknowledgment timing, completion timing."""

from __future__ import annotations

import json

from agent.tools._loader import load_table


def get_recent_dispatches(vendor_id: str, days: str = "60") -> str:
    """Return recent dispatch records for a vendor within the last N days.

    Args:
        vendor_id: Vendor ID to look up.
        days: Lookback window in days (string for tool-call compatibility).

    Returns:
        JSON-encoded list of dispatch records. May be empty or partial — the
        agent should note when coverage is incomplete.
    """
    try:
        lookback = int(days)
    except (TypeError, ValueError):
        lookback = 60

    rows = [
        d
        for d in load_table("dispatches")
        if d.get("vendor_id", "").lower() == vendor_id.lower()
        and d.get("days_ago", 999) <= lookback
    ]

    # Surface data coverage so the agent can reason about evidence sufficiency.
    coverage = {
        "vendor_id": vendor_id,
        "window_days": lookback,
        "dispatch_count": len(rows),
        "dispatches": rows,
        "coverage_note": _coverage_note(vendor_id, lookback, rows),
    }
    return json.dumps(coverage, indent=2)


def _coverage_note(vendor_id: str, lookback: int, rows: list[dict]) -> str:
    if not rows:
        return f"No dispatch records found for {vendor_id} in the last {lookback} days."
    if len(rows) < 3:
        return f"Small sample: only {len(rows)} dispatches in the window."

    # Some vendors have gaps in the synthetic data on purpose.
    last_seen = min(r.get("days_ago", 0) for r in rows)
    if last_seen > 30:
        return f"Last dispatch was {last_seen} days ago — recent activity may be missing."
    return "Coverage appears complete for the requested window."
