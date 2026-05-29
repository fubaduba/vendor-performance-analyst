"""Generate random queries and invoke the vendor-performance-analyst agent.

Loads vendor names and metadata from data/vendors.json, produces randomized
queries by combining vendor names with query templates, then calls the
Foundry hosted agent for each query. Traces are exported to Application
Insights using the OpenAI SDK + opentelemetry-instrumentation-openai-v2
which automatically records messages as span events following the GenAI
semantic conventions required for Foundry trace-based continuous evaluation.

Usage:
  python scripts/generate_random_queries.py
  python scripts/generate_random_queries.py --count 100
  python scripts/generate_random_queries.py --seed 42
"""

from __future__ import annotations

import argparse
import json
import os
import random
import sys
import time
from pathlib import Path
from uuid import uuid4

sys.path.insert(0, str(Path(__file__).parent.parent))

# Enable content recording so the instrumentor captures message bodies
os.environ.setdefault("OTEL_INSTRUMENTATION_GENAI_CAPTURE_MESSAGE_CONTENT", "true")

from dotenv import load_dotenv  # noqa: E402

load_dotenv(Path(__file__).parent.parent / ".env")

from azure.identity import DefaultAzureCredential  # noqa: E402
from openai import OpenAI  # noqa: E402
from opentelemetry import trace  # noqa: E402

REPO_ROOT = Path(__file__).parent.parent
AGENT_ID = "vendorjobdetails"
AGENT_VERSION = "19"
ENDPOINT = "https://luechen-swedencentral-foundry.services.ai.azure.com/api/projects/luechen-sc-fdp-1"
MAX_RETRIES = 2
RETRY_DELAY = 5


def _configure_tracing() -> None:
    """Configure Azure Monitor for trace-based evals.

    Uses configure_azure_monitor() to export spans to Application Insights.
    We manually emit gen_ai.user.message and gen_ai.choice span events
    because the OpenAI instrumentor does not support responses.create().
    """
    connection_string = os.environ.get("APPLICATIONINSIGHTS_CONNECTION_STRING")
    if not connection_string:
        raise SystemExit(
            "Set APPLICATIONINSIGHTS_CONNECTION_STRING in .env. "
            "Trace evaluation requires spans exported to Application Insights."
        )

    from azure.monitor.opentelemetry import configure_azure_monitor

    configure_azure_monitor(connection_string=connection_string)

# Query templates that reference a specific vendor (use {name} placeholder)
VENDOR_SPECIFIC_TEMPLATES = [
    "Give me a performance summary for {name} over the last 60 days.",
    "How is {name} performing right now?",
    "Should I be concerned about {name}?",
    "Is {name} meeting their SLA commitments?",
    "What's the trend on {name} dispatch performance?",
    "Tell me about {name} — anything I should worry about?",
    "What was {name}'s last dispatch outcome?",
    "Give me {name}'s most recent incident details.",
    "What's the latest recorded issue for {name}?",
    "How quickly did {name} close their most recent incident?",
    "What was {name}'s latest SLA result?",
    "Has {name} ever caused customer impact incidents?",
    "Is {name} a viable expansion partner for our {region} capacity?",
    "Why hasn't {name} been responsive lately?",
    "Did {name} improve after we issued the PIP?",
    "What is {name}'s average resolution time for incidents?",
    "What's the rework rate for {name}?",
    "How many dispatches has {name} had in the last 90 days?",
    "Show me {name}'s communication history.",
    "Is {name}'s contract renewal coming up soon?",
    "Compare {name}'s performance to last quarter.",
    "Would you recommend expanding {name}'s scope to {region}?",
    "What's {name}'s acknowledgment time trend?",
    "Are there any open issues with {name}?",
    "Rate {name}'s performance on a scale of 1 to 5 with justification.",
    "What evidence do we have on {name}'s quality of work?",
    "Summarize all incidents involving {name} in the last 60 days.",
    "Is {name} trending up or down?",
    "Should we put {name} on a performance improvement plan?",
    "What regions does {name} cover and how are they doing in each?",
]

# Multi-vendor / cross-cutting queries (no vendor placeholder)
CROSS_CUTTING_TEMPLATES = [
    "Are there any vendors I should escalate this quarter?",
    "Build me a vendor scorecard for the strategic vendor review meeting next week.",
    "Is there a pattern of rework across our vendors?",
    "Which vendor would you trust with an emergency fiber cut at the {region} site tonight?",
    "Which vendors are at risk of contract non-renewal?",
    "Compare our Strategic-tier vendors' recent performance.",
    "Who has the fastest average acknowledgment time?",
    "Which vendor has the highest breach rate this quarter?",
    "Rank all vendors by SLA compliance rate.",
    "Are there any regional coverage gaps we should address?",
    "Which vendors have communication gaps in the last 30 days?",
    "Summarize the overall vendor portfolio health.",
    "Who should handle our next critical dispatch at {region}?",
    "Are any vendors showing signs of improvement?",
    "Which Preferred-tier vendors are underperforming?",
]


def load_vendors() -> list[dict]:
    vendors_path = REPO_ROOT / "data" / "vendors.json"
    with open(vendors_path, "r", encoding="utf-8") as f:
        return json.loads(f.read())


def _get_openai_client(token: str) -> OpenAI:
    """Create an OpenAI client pointed at the hosted agent's Responses endpoint.

    The agent exposes the OpenAI Responses protocol, so we use the standard
    OpenAI SDK which the instrumentor traces automatically.
    """
    return OpenAI(
        api_key=token,
        base_url=f"{ENDPOINT}/agents/{AGENT_ID}/endpoint/protocols/openai",
        default_query={"api-version": "2025-05-15-preview", "version": AGENT_VERSION},
        timeout=90.0,
        max_retries=MAX_RETRIES,
    )


def generate_queries(vendors: list[dict], count: int, rng: random.Random) -> list[dict]:
    all_regions = []
    for v in vendors:
        all_regions.extend(v.get("primary_regions", []))
    all_regions = list(set(all_regions))

    queries: list[dict] = []
    for i in range(count):
        # 75% vendor-specific, 25% cross-cutting
        if rng.random() < 0.75:
            vendor = rng.choice(vendors)
            template = rng.choice(VENDOR_SPECIFIC_TEMPLATES)
            region = rng.choice(vendor.get("primary_regions", all_regions))
            query_text = template.format(name=vendor["name"], region=region)
            vendor_id = vendor["vendor_id"]
        else:
            template = rng.choice(CROSS_CUTTING_TEMPLATES)
            region = rng.choice(all_regions)
            query_text = template.format(region=region)
            vendor_id = None

        queries.append({
            "id": f"GEN-{i+1:04d}",
            "query": query_text,
            "vendor_id": vendor_id,
        })

    return queries


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate random queries and invoke the vendor-performance-analyst agent.")
    parser.add_argument(
        "--count",
        type=int,
        default=40,
        help="Number of queries to generate (default: 40)",
    )
    parser.add_argument(
        "--seed",
        type=int,
        default=None,
        help="Random seed for reproducibility",
    )
    args = parser.parse_args()

    rng = random.Random(args.seed)
    vendors = load_vendors()
    queries = generate_queries(vendors, args.count, rng)

    credential = DefaultAzureCredential()

    # Configure tracing — instruments OpenAI SDK and exports to App Insights
    _configure_tracing()
    tracer = trace.get_tracer(__name__)

    batch_run_id = str(uuid4())

    print(f"[generate+invoke] Agent: {AGENT_ID}")
    print(f"[generate+invoke] Endpoint: {ENDPOINT}")
    print(f"[generate+invoke] Queries: {len(queries)} (from {len(vendors)} vendors)")
    print()

    # Get initial token (lasts ~1 hour)
    token = credential.get_token("https://ai.azure.com/.default").token
    client = _get_openai_client(token)
    token_time = time.monotonic()

    for i, entry in enumerate(queries, 1):
        query = entry["query"]
        query_id = entry["id"]
        print(f"[{i:02d}/{len(queries)}] {query_id}: {query[:80]}...")

        # Refresh token every 45 min to avoid expiration mid-batch
        if time.monotonic() - token_time > 2700:
            try:
                token = credential.get_token("https://ai.azure.com/.default").token
                client = _get_openai_client(token)
                token_time = time.monotonic()
            except Exception as e:
                print(f"       [token refresh failed: {e}]")

        # Create an invoke_agent span with GenAI semantic conventions.
        # We manually emit gen_ai.user.message and gen_ai.choice events
        # because OpenAIInstrumentor doesn't support responses.create().
        # The continuous eval service reads these events for input/output.
        with tracer.start_as_current_span(
            "invoke_agent",
            attributes={
                "gen_ai.operation.name": "invoke_agent",
                "gen_ai.system": "az.ai.agents",
                "gen_ai.request.model": "gpt-4o",
                "gen_ai.agent.id": f"{AGENT_ID}:{AGENT_VERSION}",
                "gen_ai.agent.name": AGENT_ID,
            },
        ) as span:
            # Emit the user message event
            span.add_event(
                "gen_ai.user.message",
                attributes={
                    "gen_ai.event.content": json.dumps({"role": "user", "content": query}),
                },
            )

            try:
                response = client.responses.create(
                    model="gpt-4o",
                    input=query,
                )
                # Extract text from response output
                response_text = ""
                response_id = response.id
                for item in response.output:
                    if item.type == "message":
                        for part in item.content:
                            if part.type == "output_text":
                                response_text += part.text
                if not response_text:
                    response_text = "[no output text returned]"
            except Exception as e:
                response_text = f"[error: {e}]"
                response_id = None
                span.set_status(trace.StatusCode.ERROR, str(e))

            # Emit the assistant choice event
            span.add_event(
                "gen_ai.choice",
                attributes={
                    "gen_ai.event.content": json.dumps({
                        "finish_reason": "stop",
                        "index": 0,
                        "message": {"role": "assistant", "content": response_text},
                    }),
                },
            )

            if response_id:
                span.set_attribute("gen_ai.response.id", response_id)
            span.set_attribute("gen_ai.response.model", "gpt-4o")

        preview = response_text[:120].replace("\n", " ")
        print(f"       [{response_id or 'no-id'}] {preview}")
        time.sleep(1)

    # Flush remaining spans
    provider = trace.get_tracer_provider()
    if hasattr(provider, "force_flush"):
        provider.force_flush()

    print(f"\n[generate+invoke] Done. {len(queries)} queries invoked.")


if __name__ == "__main__":
    main()
