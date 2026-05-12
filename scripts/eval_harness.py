"""Local evaluation harness — validates the V1 vs V2 optimization gap.

Run this BEFORE the demo to confirm the score deltas are real. It invokes the
agent locally on every dataset row twice (once with V1 prompt, once with V2),
runs each row through the three evaluators, and prints a comparison table.

This is the same loop the skill drives during the demo, but run locally and
without Foundry dependencies, so you can validate the optimization gap before
stage time.

Usage:
    python scripts/eval_harness.py
    python scripts/eval_harness.py --limit 5             # smoke test
    python scripts/eval_harness.py --judge-model gpt-4o  # override judge model
    python scripts/eval_harness.py --save eval_results.json
"""

from __future__ import annotations

import argparse
import json
import os
import statistics
import sys
import textwrap
from pathlib import Path
from typing import Any

import yaml

sys.path.insert(0, str(Path(__file__).parent.parent))

from agent.agent import AGENT_TOOLS, build_agent_definition  # noqa: E402

REPO_ROOT = Path(__file__).parent.parent
DATASET_PATH = REPO_ROOT / "datasets" / "vendor_queries.jsonl"
EVALUATORS_DIR = REPO_ROOT / "evaluators"
PROMPTS_DIR = REPO_ROOT / "agent" / "prompts"


def load_dataset() -> list[dict]:
    return [json.loads(line) for line in DATASET_PATH.read_text().splitlines() if line.strip()]


def load_evaluators() -> list[dict]:
    return [yaml.safe_load(p.read_text()) for p in sorted(EVALUATORS_DIR.glob("*.yaml"))]


def get_aoai_client():
    try:
        from openai import AzureOpenAI
    except ImportError as exc:
        raise SystemExit("Install 'openai': pip install openai") from exc
    return AzureOpenAI(
        azure_endpoint=os.environ["AZURE_OPENAI_ENDPOINT"],
        api_key=os.environ["AZURE_OPENAI_API_KEY"],
        api_version="2024-08-01-preview",
    )


def invoke_agent_local(client, definition: dict, query: str, max_iters: int = 6) -> str:
    """Run the agent loop locally and return the final assistant message."""
    tool_lookup = {fn.__name__: fn for fn in AGENT_TOOLS}
    messages: list[dict[str, Any]] = [
        {"role": "system", "content": definition["instructions"]},
        {"role": "user", "content": query},
    ]
    for _ in range(max_iters):
        completion = client.chat.completions.create(
            model=definition["model"],
            messages=messages,
            tools=definition["tools"],
        )
        msg = completion.choices[0].message
        if not msg.tool_calls:
            return msg.content or ""
        messages.append(msg.model_dump())
        for tc in msg.tool_calls:
            tool_args = json.loads(tc.function.arguments or "{}")
            result = tool_lookup[tc.function.name](**tool_args)
            messages.append({"role": "tool", "tool_call_id": tc.id, "content": str(result)})
    return "(agent did not converge)"


def run_judge(client, judge_model: str, evaluator: dict, row: dict, response: str) -> dict:
    """Run an LLM-as-judge evaluator against one row/response pair."""
    judge_input = {
        "query": row["query"],
        "response": response,
        "evidence_quality": row.get("evidence_quality"),
        "expected_behavior": row.get("expected_behavior"),
        "reference_facts": row.get("reference_facts"),
    }
    completion = client.chat.completions.create(
        model=judge_model,
        messages=[
            {"role": "system", "content": evaluator["instructions"]},
            {"role": "user", "content": json.dumps(judge_input, indent=2)},
        ],
        response_format={"type": "json_object"},
    )
    try:
        return json.loads(completion.choices[0].message.content)
    except (json.JSONDecodeError, TypeError):
        return {"score": 0.0, "reasoning": "Judge returned non-JSON output"}


def run_one_prompt(client, definition: dict, dataset: list[dict],
                   evaluators: list[dict], judge_model: str, label: str) -> list[dict]:
    """Run the agent on every dataset row and score with every evaluator."""
    results = []
    for i, row in enumerate(dataset, 1):
        print(f"  [{label}] {i:>2}/{len(dataset)} {row['id']} ...", end=" ", flush=True)
        try:
            response = invoke_agent_local(client, definition, row["query"])
        except Exception as exc:  # noqa: BLE001
            response = f"(error invoking agent: {exc})"
        scores = {}
        for ev in evaluators:
            judge = run_judge(client, judge_model, ev, row, response)
            scores[ev["name"]] = judge
        print("ok")
        results.append({
            "id": row["id"],
            "query": row["query"],
            "evidence_quality": row.get("evidence_quality"),
            "response": response,
            "scores": scores,
        })
    return results


def aggregate(results: list[dict], evaluator_names: list[str]) -> dict[str, dict]:
    """Compute mean score per evaluator, overall and per evidence-quality bucket."""
    buckets: dict[str, list[float]] = {f"overall::{e}": [] for e in evaluator_names}
    for r in results:
        for e in evaluator_names:
            score = r["scores"][e].get("score", 0.0)
            buckets[f"overall::{e}"].append(float(score))
            eq = r.get("evidence_quality") or "unknown"
            buckets.setdefault(f"{eq}::{e}", []).append(float(score))
    return {k: {"mean": statistics.mean(v) if v else 0.0, "n": len(v)} for k, v in buckets.items()}


def print_comparison(v1_agg: dict, v2_agg: dict, evaluator_names: list[str]) -> None:
    print()
    print("=" * 78)
    print("OVERALL — mean evaluator score")
    print("=" * 78)
    print(f"{'evaluator':<28}{'V1':>10}{'V2':>10}{'delta':>10}")
    print("-" * 78)
    for e in evaluator_names:
        k = f"overall::{e}"
        v1, v2 = v1_agg[k]["mean"], v2_agg[k]["mean"]
        print(f"{e:<28}{v1:>10.3f}{v2:>10.3f}{(v2 - v1):>+10.3f}")

    print()
    print("=" * 78)
    print("BY EVIDENCE QUALITY — where the optimization should pay off most")
    print("=" * 78)
    print(f"{'bucket / evaluator':<40}{'V1':>10}{'V2':>10}{'delta':>10}")
    print("-" * 78)
    for eq in ["high", "partial", "sparse", "conflicting"]:
        for e in evaluator_names:
            k = f"{eq}::{e}"
            if k not in v1_agg or v1_agg[k]["n"] == 0:
                continue
            v1, v2 = v1_agg[k]["mean"], v2_agg[k]["mean"]
            label = f"  {eq} / {e}"
            print(f"{label:<40}{v1:>10.3f}{v2:>10.3f}{(v2 - v1):>+10.3f}")
        print()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--limit", type=int, help="Only run first N rows (for smoke testing)")
    parser.add_argument("--judge-model", default=os.environ.get("JUDGE_MODEL", "gpt-4o"))
    parser.add_argument("--save", help="Write raw results to this JSON path")
    args = parser.parse_args()

    client = get_aoai_client()
    dataset = load_dataset()
    if args.limit:
        dataset = dataset[: args.limit]
    evaluators = load_evaluators()
    evaluator_names = [e["name"] for e in evaluators]

    print(f"Dataset rows: {len(dataset)}")
    print(f"Evaluators:   {evaluator_names}")
    print(f"Judge model:  {args.judge_model}")
    print()

    print("Running V1...")
    os.environ["SYSTEM_PROMPT_PATH"] = str(PROMPTS_DIR / "system_prompt_v1.md")
    v1_def = build_agent_definition()
    v1_results = run_one_prompt(client, v1_def, dataset, evaluators, args.judge_model, "V1")

    print()
    print("Running V2...")
    os.environ["SYSTEM_PROMPT_PATH"] = str(PROMPTS_DIR / "system_prompt_v2.md")
    v2_def = build_agent_definition()
    v2_results = run_one_prompt(client, v2_def, dataset, evaluators, args.judge_model, "V2")

    v1_agg = aggregate(v1_results, evaluator_names)
    v2_agg = aggregate(v2_results, evaluator_names)
    print_comparison(v1_agg, v2_agg, evaluator_names)

    print()
    print(textwrap.dedent("""
        How to read this:
          - Fairness & Calibration overall should be markedly higher for V2.
          - The biggest deltas should be in the 'partial', 'sparse', and
            'conflicting' buckets. Those are the rows where V1's overconfidence
            problem shows up. The 'high' bucket should be roughly unchanged.
          - If V1 and V2 are within ~0.05 overall on Fairness, the optimization
            gap is too small for the live demo. Either harden V1 (make it more
            overconfident) or sharpen V2 (more explicit uncertainty rules).
    """).strip())

    if args.save:
        Path(args.save).write_text(
            json.dumps({"v1": v1_results, "v2": v2_results, "v1_agg": v1_agg, "v2_agg": v2_agg}, indent=2)
        )
        print(f"\nRaw results -> {args.save}")


if __name__ == "__main__":
    main()
