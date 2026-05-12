"""Seed traces by invoking the deployed agent on the eval dataset.

Run this before the demo so the traces -> dataset step has real traces to
filter. Iterates the eval dataset and invokes the hosted agent for each row.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from agent.agent import AGENT_NAME, get_project_client  # noqa: E402

DATASET_PATH = Path(__file__).parent.parent / "datasets" / "vendor_queries.jsonl"


def load_queries(limit: int) -> list[dict]:
    rows = [json.loads(line) for line in DATASET_PATH.read_text().splitlines() if line.strip()]
    # Cycle through the dataset if the caller asks for more invocations than
    # we have queries.
    out: list[dict] = []
    i = 0
    while len(out) < limit:
        out.append(rows[i % len(rows)])
        i += 1
    return out


def invoke_agent(project_client, agent_id: str, query: str) -> None:
    """Invoke the agent. Each invocation produces a trace."""
    thread = project_client.agents.create_thread()
    project_client.agents.create_message(
        thread_id=thread.id,
        role="user",
        content=query,
    )
    run = project_client.agents.create_and_process_run(
        thread_id=thread.id,
        agent_id=agent_id,
    )
    # Best-effort wait — adjust for your environment.
    deadline = time.time() + 60
    while time.time() < deadline and getattr(run, "status", None) not in ("completed", "failed"):
        time.sleep(2)
        run = project_client.agents.get_run(thread_id=thread.id, run_id=run.id)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--count", type=int, default=30, help="Number of invocations")
    args = parser.parse_args()

    project_client = get_project_client()
    foundry_json = Path(__file__).parent.parent / "foundry.json"
    if not foundry_json.exists():
        raise SystemExit("foundry.json missing — run scripts/deploy.py first.")
    config = json.loads(foundry_json.read_text())
    agent_id = config["agent_id"]

    queries = load_queries(args.count)
    print(f"[seed] Invoking {AGENT_NAME} {len(queries)} times...")
    for i, row in enumerate(queries, 1):
        try:
            invoke_agent(project_client, agent_id, row["query"])
            print(f"[seed] {i:>3}/{len(queries)} ok — {row['id']}")
        except Exception as exc:  # noqa: BLE001
            print(f"[seed] {i:>3}/{len(queries)} ERROR — {row['id']}: {exc}")
        time.sleep(1)
    print("[seed] Done. Traces should be visible in the Foundry portal and queryable via the skill.")


if __name__ == "__main__":
    main()
