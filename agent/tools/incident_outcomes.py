"""Resolution times, repeat issue tracking, customer impact."""

from __future__ import annotations

import json

from agent.tools._loader import load_table


def get_incident_outcomes(vendor_id: str, days: str = "90") -> str:
    """Return incidents the vendor was involved in and their outcomes."""
    try:
        lookback = int(days)
    except (TypeError, ValueError):
        lookback = 90

    rows = [
        i
        for i in load_table("incident_outcomes")
        if i.get("vendor_id", "").lower() == vendor_id.lower()
        and i.get("days_ago", 999) <= lookback
    ]

    return json.dumps(
        {
            "vendor_id": vendor_id,
            "window_days": lookback,
            "incident_count": len(rows),
            "incidents": rows,
            "coverage_note": (
                f"No incident records found for {vendor_id} in the last {lookback} days."
                if not rows
                else f"{len(rows)} incidents on file in the window."
            ),
        },
        indent=2,
    )
