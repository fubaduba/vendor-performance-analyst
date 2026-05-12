"""Deploy the Vendor Performance Analyst to Foundry as a hosted agent.

Reads the agent definition from agent.agent.build_agent_definition() and
calls the Foundry Agents API to create or update the agent. Also registers
the evaluators and dataset so the skill can pick them up.
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

# Allow running this script from the repo root.
sys.path.insert(0, str(Path(__file__).parent.parent))

from agent.agent import (  # noqa: E402
    AGENT_NAME,
    build_agent_definition,
    get_project_client,
)

REPO_ROOT = Path(__file__).parent.parent
DATASET_PATH = REPO_ROOT / "datasets" / "vendor_queries.jsonl"
EVALUATORS_DIR = REPO_ROOT / "evaluators"


def deploy_agent() -> str:
    """Create or update the hosted agent. Returns the agent ID."""
    project_client = get_project_client()
    definition = build_agent_definition()

    print(f"[deploy] Agent name: {definition['name']}")
    print(f"[deploy] Model: {definition['model']}")
    print(f"[deploy] Tool count: {len(definition['tools'])}")
    print(f"[deploy] Prompt length: {len(definition['instructions'])} chars")

    # The exact SDK surface varies by Foundry release. We use the agents
    # client and handle both create-new and update-existing.
    agents_client = project_client.agents

    existing = _find_existing_agent(agents_client, definition["name"])
    if existing:
        print(f"[deploy] Updating existing agent: {existing.id}")
        agents_client.update_agent(
            agent_id=existing.id,
            model=definition["model"],
            instructions=definition["instructions"],
            tools=definition["tools"],
            metadata=definition["metadata"],
        )
        return existing.id

    print("[deploy] Creating new agent")
    created = agents_client.create_agent(
        name=definition["name"],
        model=definition["model"],
        instructions=definition["instructions"],
        tools=definition["tools"],
        metadata=definition["metadata"],
    )
    return created.id


def register_dataset(project_client) -> str:
    """Register vendor_queries.jsonl as a Foundry dataset."""
    print(f"[deploy] Registering dataset: {DATASET_PATH.name}")
    # Format and signature vary by SDK; left as a single call site for clarity.
    dataset_name = "vendor_performance_queries_v1"
    project_client.datasets.upload_file(
        name=dataset_name,
        file_path=str(DATASET_PATH),
    )
    return dataset_name


def register_evaluators(project_client) -> list[str]:
    """Register each evaluator YAML as a Foundry evaluator."""
    registered: list[str] = []
    for yaml_path in sorted(EVALUATORS_DIR.glob("*.yaml")):
        print(f"[deploy] Registering evaluator: {yaml_path.name}")
        project_client.evaluators.create_or_update_from_file(str(yaml_path))
        registered.append(yaml_path.stem)
    return registered


def update_foundry_json(agent_id: str, dataset_name: str, evaluators: list[str]) -> None:
    """Update foundry.json so the skill has context without re-prompting."""
    foundry_json = REPO_ROOT / "foundry.json"
    config = {
        "project_endpoint": os.environ["AZURE_AI_PROJECT_ENDPOINT"],
        "agent_id": agent_id,
        "agent_name": AGENT_NAME,
        "default_dataset": dataset_name,
        "default_evaluators": evaluators,
    }
    foundry_json.write_text(json.dumps(config, indent=2), encoding="utf-8")
    print(f"[deploy] Wrote {foundry_json}")


def main() -> None:
    agent_id = deploy_agent()
    project_client = get_project_client()
    dataset_name = register_dataset(project_client)
    evaluators = register_evaluators(project_client)
    update_foundry_json(agent_id, dataset_name, evaluators)
    print()
    print(f"[deploy] Done. Agent ID: {agent_id}")
    print("[deploy] Next: python scripts/seed_traces.py --count 30")


def _find_existing_agent(agents_client, name: str):
    for agent in agents_client.list_agents():
        if getattr(agent, "name", None) == name:
            return agent
    return None


if __name__ == "__main__":
    main()
