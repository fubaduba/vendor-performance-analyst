"""Teams/email thread summaries from Work IQ."""

from __future__ import annotations

import json

from agent.tools._loader import load_table


def get_communications_summary(vendor_id: str, days: str = "60") -> str:
    """Return summarized Teams and email threads with a vendor.

    Some vendors have intentionally sparse or missing communications data —
    the agent should flag this rather than assume silence means alignment.
    """
    try:
        lookback = int(days)
    except (TypeError, ValueError):
        lookback = 60

    rows = [
        c
        for c in load_table("communications")
        if c.get("vendor_id", "").lower() == vendor_id.lower()
        and c.get("days_ago", 999) <= lookback
    ]

    last_seen = min((r.get("days_ago", 999) for r in rows), default=None)
    coverage_note = (
        f"No communications recorded in the last {lookback} days."
        if not rows
        else f"Most recent communication: {last_seen} days ago."
        if last_seen and last_seen > 30
        else "Communications coverage appears current."
    )

    return json.dumps(
        {
            "vendor_id": vendor_id,
            "window_days": lookback,
            "thread_count": len(rows),
            "threads": rows,
            "coverage_note": coverage_note,
        },
        indent=2,
    )
