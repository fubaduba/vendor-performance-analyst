"""SLA targets, breach records, response time history."""

from __future__ import annotations

import json

from agent.tools._loader import load_table


def get_sla_record(vendor_id: str) -> str:
    """Return SLA targets, breaches, and response time stats for a vendor."""
    for record in load_table("sla_records"):
        if record["vendor_id"].lower() == vendor_id.lower():
            return json.dumps(record, indent=2)
    return json.dumps(
        {
            "vendor_id": vendor_id,
            "error": "No SLA record found for this vendor",
            "coverage_note": "SLA tracking may not be configured for this vendor.",
        }
    )
