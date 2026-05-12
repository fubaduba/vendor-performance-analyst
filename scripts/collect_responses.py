"""Collect agent responses for all dataset queries and write eval-ready JSONL.

Uses the Foundry Agent responses API to invoke vendor-performance-analyst
for each row in datasets/vendor_queries.jsonl, then writes
scripts/eval_responses.jsonl with query + response + eval fields.

Usage:
    python scripts/collect_responses.py
"""

from __future__ import annotations

import json
import os
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from dotenv import load_dotenv  # noqa: E402

load_dotenv(Path(__file__).parent.parent / ".env")

from azure.ai.projects import AIProjectClient  # noqa: E402
from azure.identity import DefaultAzureCredential  # noqa: E402

REPO_ROOT = Path(__file__).parent.parent
DATASET_PATH = REPO_ROOT / "datasets" / "vendor_queries.jsonl"
OUTPUT_PATH = REPO_ROOT / "scripts" / "eval_responses.jsonl"
AGENT_NAME = "vendor-performance-analyst"


def invoke_agent(client: AIProjectClient, query: str) -> str:
    """Invoke the agent via the responses API and return the final text."""
    endpoint = os.environ["AZURE_AI_PROJECT_ENDPOINT"].strip()
    response = client._http_client.post(
        f"{endpoint}/agents/{AGENT_NAME}/responses",
        json={"input": [{"role": "user", "content": query}]},
        headers={"Content-Type": "application/json"},
    )
    response.raise_for_status()
    data = response.json()
    # Extract the last assistant message text
    for item in reversed(data.get("output", [])):
        if item.get("role") == "assistant":
            content = item.get("content", [])
            for c in content:
                if c.get("type") == "output_text":
                    return c["text"]
    return str(data)


def main() -> None:
    dataset = [json.loads(line) for line in DATASET_PATH.read_text().splitlines() if line.strip()]

    endpoint = os.environ["AZURE_AI_PROJECT_ENDPOINT"].strip()
    print(f"Project: {endpoint}")
    print(f"Agent: {AGENT_NAME}")
    print(f"Queries: {len(dataset)}")
    print()

    from openai import AzureOpenAI
    # Use openai client directly against the Foundry responses API
    # The project endpoint acts as a base URL for agent invocation
    # Foundry agent responses endpoint: POST /agents/{name}/responses
    import httpx
    from azure.identity import DefaultAzureCredential, get_bearer_token_provider

    credential = DefaultAzureCredential()
    token_provider = get_bearer_token_provider(
        credential, "https://ai.azure.com/.default"
    )

    results = []
    for i, row in enumerate(dataset, 1):
        query = row["query"]
        print(f"[{i:02d}/{len(dataset)}] {query[:70]}...")

        token = credential.get_token("https://ai.azure.com/.default").token
        resp = httpx.post(
            f"{endpoint}/agents/{AGENT_NAME}/responses",
            headers={
                "Authorization": f"Bearer {token}",
                "Content-Type": "application/json",
            },
            json={"input": [{"role": "user", "content": query}]},
            timeout=60,
        )
        resp.raise_for_status()
        data = resp.json()

        # Extract final assistant message
        response_text = ""
        for item in reversed(data.get("output", [])):
            content = item.get("content", [])
            for c in (content if isinstance(content, list) else []):
                if c.get("type") == "output_text" and c.get("text"):
                    response_text = c["text"]
                    break
            if response_text:
                break

        result = {
            "query": query,
            "response": response_text,
            "evidence_quality": row.get("evidence_quality", ""),
            "expected_behavior": row.get("expected_behavior", ""),
            "reference_facts": row.get("reference_facts", ""),
        }
        results.append(result)
        print(f"       verdict preview: {response_text[:80].replace(chr(10), ' ')}")
        time.sleep(0.5)  # gentle throttle

    OUTPUT_PATH.write_text(
        "\n".join(json.dumps(r) for r in results) + "\n",
        encoding="utf-8",
    )
    print(f"\nWrote {len(results)} rows to {OUTPUT_PATH}")


if __name__ == "__main__":
    main()
