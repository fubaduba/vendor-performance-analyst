"""Vendor metadata and contract lookup."""

from __future__ import annotations

import json

from agent.tools._loader import load_table


def get_vendor(vendor_id: str) -> str:
    """Return vendor metadata, contract terms, and performance tier."""
    for v in load_table("vendors"):
        if v["vendor_id"].lower() == vendor_id.lower() or v["name"].lower() == vendor_id.lower():
            return json.dumps(v, indent=2)
    return json.dumps({"error": f"Vendor '{vendor_id}' not found"})
