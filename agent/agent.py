"""Vendor Performance Analyst agent definition.

Loads the system prompt from an environment variable (the FAOS knob) and
registers the operational-data tools. Built for the Foundry Agent Service
hosted-agent runtime, but the same module also runs locally via
scripts/local_run.py.
"""

from __future__ import annotations

import os
from pathlib import Path

from azure.ai.projects import AIProjectClient
from azure.identity import DefaultAzureCredential

from agent.tools import (
    communications,
    dispatch_history,
    incident_outcomes,
    sla_records,
    vendor_lookup,
)

AGENT_NAME = "vendor-performance-analyst"
MODEL_DEPLOYMENT = os.environ.get("MODEL_DEPLOYMENT_NAME", "gpt-4o")
DEFAULT_PROMPT_PATH = Path(__file__).parent / "prompts" / "system_prompt_v1.md"


def load_system_prompt() -> str:
    """Load the system prompt.

    Resolution order:
      1. SYSTEM_PROMPT_TEXT env var (FAOS sets this directly when optimizing)
      2. SYSTEM_PROMPT_PATH env var (path to a prompt file)
      3. agent/prompts/system_prompt_v1.md (default)

    This is the primary FAOS knob. Adding more knobs (temperature, tool gating
    thresholds, etc.) means reading additional env vars here.
    """
    if text := os.environ.get("SYSTEM_PROMPT_TEXT"):
        return text

    if path_override := os.environ.get("SYSTEM_PROMPT_PATH"):
        return Path(path_override).read_text(encoding="utf-8")

    return DEFAULT_PROMPT_PATH.read_text(encoding="utf-8")


# Tool registry — these are the Python functions Foundry Agent Service will
# expose to the model as callable tools.
AGENT_TOOLS = [
    vendor_lookup.get_vendor,
    dispatch_history.get_recent_dispatches,
    sla_records.get_sla_record,
    communications.get_communications_summary,
    incident_outcomes.get_incident_outcomes,
]


def build_agent_definition() -> dict:
    """Return the declarative agent definition consumed by scripts/deploy.py."""
    return {
        "name": AGENT_NAME,
        "model": MODEL_DEPLOYMENT,
        "instructions": load_system_prompt(),
        "tools": [_tool_schema(fn) for fn in AGENT_TOOLS],
        "metadata": {
            "version": os.environ.get("AGENT_VERSION", "v1"),
            "purpose": "Vendor performance analysis for data center operations",
            "demo": "BRK252-Act-II",
        },
    }


def _tool_schema(fn) -> dict:
    """Build a function-tool schema from a Python callable's annotations."""
    import inspect

    sig = inspect.signature(fn)
    properties: dict[str, dict] = {}
    required: list[str] = []
    for name, param in sig.parameters.items():
        properties[name] = {"type": "string", "description": f"Argument {name}"}
        if param.default is inspect.Parameter.empty:
            required.append(name)

    return {
        "type": "function",
        "function": {
            "name": fn.__name__,
            "description": (fn.__doc__ or "").strip().split("\n")[0],
            "parameters": {
                "type": "object",
                "properties": properties,
                "required": required,
            },
        },
    }


def get_project_client() -> AIProjectClient:
    endpoint = os.environ["AZURE_AI_PROJECT_ENDPOINT"]
    return AIProjectClient(endpoint=endpoint, credential=DefaultAzureCredential())


if __name__ == "__main__":
    import json

    print(json.dumps(build_agent_definition(), indent=2))
