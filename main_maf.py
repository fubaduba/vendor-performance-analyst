"""Vendor Performance Analyst — Foundry hosted agent entry point (MAF).

Uses Microsoft Agent Framework (MAF) with the Foundry hosting adapter.
The framework handles the model+tool loop, conversation management, and
tracing automatically.

Required environment variables (injected by Foundry at runtime):
    FOUNDRY_PROJECT_ENDPOINT   (or AZURE_AI_PROJECT_ENDPOINT)
    AZURE_AI_MODEL_DEPLOYMENT_NAME  (or MODEL_DEPLOYMENT_NAME)
"""

from __future__ import annotations

import os
from typing import Annotated

from dotenv import load_dotenv

load_dotenv(override=False)

from agent_framework import Agent, tool
from agent_framework.openai import OpenAIChatClient
from agent_framework_foundry_hosting import ResponsesHostServer
from azure.identity import DefaultAzureCredential

from agent.agent import load_system_prompt
from agent.tools._loader import load_table

# ── Configuration ─────────────────────────────────────────────────────────────

FOUNDRY_PROJECT_ENDPOINT: str = os.environ.get(
    "FOUNDRY_PROJECT_ENDPOINT", ""
) or os.environ.get("AZURE_AI_PROJECT_ENDPOINT", "")

MODEL_DEPLOYMENT: str = os.environ.get(
    "AZURE_AI_MODEL_DEPLOYMENT_NAME", ""
) or os.environ.get("MODEL_DEPLOYMENT_NAME", "gpt-4o")

SYSTEM_PROMPT = load_system_prompt()


# ── Tools (decorated for MAF) ────────────────────────────────────────────────

import json


@tool
def get_vendor(
    vendor_id: Annotated[str, "Vendor ID or name to look up"],
) -> str:
    """Return vendor metadata, contract terms, and performance tier."""
    for v in load_table("vendors"):
        if v["vendor_id"].lower() == vendor_id.lower() or v["name"].lower() == vendor_id.lower():
            return json.dumps(v, indent=2)
    return json.dumps({"error": f"Vendor '{vendor_id}' not found"})


@tool
def get_recent_dispatches(
    vendor_id: Annotated[str, "Vendor ID to look up"],
    days: Annotated[int, "Lookback window in days"] = 60,
) -> str:
    """Return recent dispatch records for a vendor within the last N days."""
    rows = [
        d
        for d in load_table("dispatches")
        if d.get("vendor_id", "").lower() == vendor_id.lower()
        and d.get("days_ago", 999) <= days
    ]

    if not rows:
        coverage_note = f"No dispatch records found for {vendor_id} in the last {days} days."
    elif len(rows) < 3:
        coverage_note = f"Small sample: only {len(rows)} dispatches in the window."
    else:
        coverage_note = f"{len(rows)} dispatches in the window — reasonable coverage."

    return json.dumps(
        {
            "vendor_id": vendor_id,
            "window_days": days,
            "dispatch_count": len(rows),
            "dispatches": rows,
            "coverage_note": coverage_note,
        },
        indent=2,
    )


@tool
def get_sla_record(
    vendor_id: Annotated[str, "Vendor ID to look up"],
) -> str:
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


@tool
def get_communications_summary(
    vendor_id: Annotated[str, "Vendor ID to look up"],
    days: Annotated[int, "Lookback window in days"] = 60,
) -> str:
    """Return summarized Teams and email threads with a vendor."""
    rows = [
        c
        for c in load_table("communications")
        if c.get("vendor_id", "").lower() == vendor_id.lower()
        and c.get("days_ago", 999) <= days
    ]

    last_seen = min((r.get("days_ago", 999) for r in rows), default=None)
    if not rows:
        coverage_note = f"No communications recorded in the last {days} days."
    elif last_seen and last_seen > 30:
        coverage_note = f"Most recent communication: {last_seen} days ago."
    else:
        coverage_note = "Communications coverage appears current."

    return json.dumps(
        {
            "vendor_id": vendor_id,
            "window_days": days,
            "thread_count": len(rows),
            "threads": rows,
            "coverage_note": coverage_note,
        },
        indent=2,
    )


@tool
def get_incident_outcomes(
    vendor_id: Annotated[str, "Vendor ID to look up"],
    days: Annotated[int, "Lookback window in days"] = 90,
) -> str:
    """Return incidents the vendor was involved in and their outcomes."""
    rows = [
        i
        for i in load_table("incident_outcomes")
        if i.get("vendor_id", "").lower() == vendor_id.lower()
        and i.get("days_ago", 999) <= days
    ]

    return json.dumps(
        {
            "vendor_id": vendor_id,
            "window_days": days,
            "incident_count": len(rows),
            "incidents": rows,
            "coverage_note": (
                f"No incident records found for {vendor_id} in the last {days} days."
                if not rows
                else f"{len(rows)} incidents on file in the window."
            ),
        },
        indent=2,
    )


# ── Agent definition ─────────────────────────────────────────────────────────

from azure.ai.projects import AIProjectClient
from openai import AsyncOpenAI

_credential = DefaultAzureCredential()
_project_client = AIProjectClient(endpoint=FOUNDRY_PROJECT_ENDPOINT, credential=_credential)
_openai_client = _project_client.get_openai_client()

# Wrap the sync token provider to be async-compatible
_sync_token_provider = _openai_client._api_key_provider


async def _async_token_provider() -> str:
    return _sync_token_provider()


# Wrap the sync OpenAI client into an AsyncOpenAI with the same config
_async_openai = AsyncOpenAI(
    base_url=str(_openai_client.base_url),
    api_key=_async_token_provider,
    default_query=_openai_client._custom_query,
)

client = OpenAIChatClient(
    model=MODEL_DEPLOYMENT,
    async_client=_async_openai,
)

agent = Agent(
    client=client,
    name="vendorjobdetails",
    instructions=SYSTEM_PROMPT,
    tools=[
        get_vendor,
        get_recent_dispatches,
        get_sla_record,
        get_communications_summary,
        get_incident_outcomes,
    ],
)

# ── Foundry hosting adapter ──────────────────────────────────────────────────

app = ResponsesHostServer(agent)

if __name__ == "__main__":
    app.run()
