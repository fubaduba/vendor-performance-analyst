"""Local evaluation harness — mirrors evaluation_agent_batch_eval_create.

Loads evaluator YAMLs from the catalog schema (name, category, scoringType,
promptText, minScore, maxScore, passThreshold), runs the agent on each dataset
row, scores with each evaluator, and emits a report shaped like the output of
evaluation_agent_batch_eval_create.

Usage:
    python scripts/eval_harness.py
    python scripts/eval_harness.py --limit 5             # smoke test
    python scripts/eval_harness.py --judge-model gpt-4o  # override judge model
"""

from __future__ import annotations

import argparse
import json
import os
import re
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

REQUIRED_EVAL_KEYS = {
    "name", "category", "scoringType", "promptText",
    "minScore", "maxScore", "passThreshold",
}


# ── Data loading ─────────────────────────────────────────────────────────────

def load_dataset() -> list[dict]:
    rows = [json.loads(line) for line in DATASET_PATH.read_text().splitlines() if line.strip()]
    for i, row in enumerate(rows):
        for col in ("query", "ground_truth", "context"):
            if col not in row:
                raise KeyError(
                    f"Dataset row {i} is missing required column '{col}'. "
                    "Expected columns: query, ground_truth, context, evidence_quality."
                )
    return rows


def load_evaluators() -> list[dict]:
    evaluators = []
    for p in sorted(EVALUATORS_DIR.glob("*.yaml")):
        ev = yaml.safe_load(p.read_text())
        missing = REQUIRED_EVAL_KEYS - set(ev.keys())
        if missing:
            raise ValueError(
                f"Evaluator {p.name} is missing required keys: {sorted(missing)}. "
                "Evaluator YAMLs must use the catalog schema."
            )
        evaluators.append(ev)
    return evaluators


# ── Client construction ───────────────────────────────────────────────────────

def get_client():
    """Build an OpenAI-compatible client using DefaultAzureCredential + FOUNDRY_PROJECT_ENDPOINT.

    Falls back to direct AzureOpenAI for local dev when only
    AZURE_OPENAI_ENDPOINT + AZURE_OPENAI_API_KEY are available.
    """
    endpoint = os.environ.get("FOUNDRY_PROJECT_ENDPOINT") or os.environ.get(
        "AZURE_AI_PROJECT_ENDPOINT"
    )
    if endpoint:
        from azure.ai.projects import AIProjectClient
        from azure.identity import DefaultAzureCredential

        project_client = AIProjectClient(
            endpoint=endpoint, credential=DefaultAzureCredential()
        )
        return project_client.get_openai_client()

    # Local dev fallback
    aoai_endpoint = os.environ.get("AZURE_OPENAI_ENDPOINT")
    aoai_key = os.environ.get("AZURE_OPENAI_API_KEY")
    if not aoai_endpoint or not aoai_key:
        raise EnvironmentError(
            "Set FOUNDRY_PROJECT_ENDPOINT (or AZURE_AI_PROJECT_ENDPOINT) "
            "or AZURE_OPENAI_ENDPOINT + AZURE_OPENAI_API_KEY"
        )
    from openai import AzureOpenAI

    return AzureOpenAI(
        azure_endpoint=aoai_endpoint,
        api_key=aoai_key,
        api_version="2024-08-01-preview",
    )


def get_model_name() -> str:
    return (
        os.environ.get("AZURE_AI_MODEL_DEPLOYMENT_NAME")
        or os.environ.get("MODEL_DEPLOYMENT_NAME")
        or "gpt-4o"
    )


# ── Agent invocation ──────────────────────────────────────────────────────────

def invoke_agent(client, definition: dict, query: str, max_iters: int = 6) -> str:
    """Run the agent tool loop and return the final assistant message."""
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


# ── Evaluator execution ───────────────────────────────────────────────────────

def render_prompt(
    prompt_text: str,
    query: str,
    response: str,
    ground_truth: str,
    context: str,
) -> str:
    """Substitute {{placeholder}} tokens in promptText."""
    return (
        prompt_text
        .replace("{{query}}", query)
        .replace("{{response}}", response)
        .replace("{{ground_truth}}", ground_truth)
        .replace("{{context}}", context)
    )


def parse_score(text: str, min_score: int, max_score: int) -> int:
    """Extract an integer score from judge output in [min_score, max_score].

    Looks for a bare integer in the judge's reply that falls within the valid
    range before falling back to a pattern that clamps any integer found.
    Logs a warning when no parseable integer is found so malformed replies are
    visible in the output.
    """
    stripped = text.strip()
    # Prefer a digit that is already within the valid range.
    in_range = re.findall(
        rf"\b([{min_score}-{max_score}])\b" if max_score <= 9 else r"\b(\d+)\b",
        stripped,
    )
    for token in in_range:
        try:
            value = int(token)
            if min_score <= value <= max_score:
                return value
        except ValueError:
            continue
    # Fallback: clamp any integer found.
    any_int = re.findall(r"\b(\d+)\b", stripped)
    if any_int:
        try:
            return max(min_score, min(max_score, int(any_int[0])))
        except ValueError:
            pass
    import logging as _logging
    _logging.getLogger(__name__).warning(
        "parse_score: could not extract integer from judge reply (length=%d); "
        "falling back to midpoint %d. Reply prefix: %.80r",
        len(text),
        (min_score + max_score) // 2,
        text[:80],
    )
    return (min_score + max_score) // 2


def score_row(
    client,
    judge_model: str,
    evaluator: dict,
    row: dict,
    response: str,
) -> dict:
    """Score one (evaluator, row, response) triple."""
    prompt = render_prompt(
        evaluator["promptText"],
        query=row["query"],
        response=response,
        ground_truth=row.get("ground_truth", ""),
        context=row.get("context", ""),
    )
    completion = client.chat.completions.create(
        model=judge_model,
        messages=[{"role": "user", "content": prompt}],
    )
    reply = completion.choices[0].message.content or ""
    score = parse_score(reply, evaluator["minScore"], evaluator["maxScore"])
    passed = score >= evaluator["passThreshold"]
    return {"score": score, "passed": passed, "reasoning": reply[:300]}


# ── Eval loop ─────────────────────────────────────────────────────────────────

def run_eval(
    client,
    definition: dict,
    dataset: list[dict],
    evaluators: list[dict],
    judge_model: str,
    label: str,
) -> list[dict]:
    """Run agent on every dataset row and score with every evaluator."""
    rows_out = []
    for i, row in enumerate(dataset, 1):
        print(f"  [{label}] {i:>2}/{len(dataset)} {row['id']} ...", end=" ", flush=True)
        try:
            response = invoke_agent(client, definition, row["query"])
        except Exception as exc:  # noqa: BLE001
            response = f"(error invoking agent: {exc})"
        scores: dict[str, dict] = {}
        for ev in evaluators:
            try:
                scores[ev["name"]] = score_row(client, judge_model, ev, row, response)
            except Exception as exc:  # noqa: BLE001
                scores[ev["name"]] = {
                    "score": ev["minScore"],
                    "passed": False,
                    "reasoning": f"Judge error: {exc}",
                }
        print("ok")
        rows_out.append(
            {
                "row_index": i,
                "id": row["id"],
                "query": row["query"],
                "evidence_quality": row.get("evidence_quality"),
                "response": response,
                "scores": scores,
            }
        )
    return rows_out


# ── Aggregation ───────────────────────────────────────────────────────────────

def aggregate(results: list[dict], evaluators: list[dict]) -> dict[str, dict]:
    """Compute per-evaluator mean score, pass rate, and count."""
    summary: dict[str, dict] = {}
    for ev in evaluators:
        name = ev["name"]
        all_scores = [r["scores"][name]["score"] for r in results]
        passed = [r["scores"][name]["passed"] for r in results]
        summary[name] = {
            "mean_score": statistics.mean(all_scores) if all_scores else 0.0,
            "pass_rate": sum(passed) / len(passed) if passed else 0.0,
            "count": len(all_scores),
            "pass_threshold": ev["passThreshold"],
        }
    return summary


# ── Reporting ─────────────────────────────────────────────────────────────────

def print_report(
    label: str,
    results: list[dict],
    summary: dict[str, dict],
    evaluators: list[dict],
) -> None:
    """Print a per-evaluator summary and per-row breakdown."""
    eval_names = [ev["name"] for ev in evaluators]
    col_w = 20

    print()
    print("=" * 78)
    print(f"EVALUATION REPORT — {label}")
    print("=" * 78)

    # Per-evaluator summary table
    print(f"\n{'Evaluator':<28}{'Mean':>8}{'Pass%':>8}{'Count':>8}{'Threshold':>10}")
    print("-" * 62)
    for ev in evaluators:
        name = ev["name"]
        s = summary[name]
        print(
            f"{name:<28}{s['mean_score']:>8.2f}"
            f"{s['pass_rate'] * 100:>7.1f}%"
            f"{s['count']:>8}{s['pass_threshold']:>10}"
        )

    # Per-row breakdown
    header_query = "Query"
    print(f"\n{'#':<4}{'ID':<8}{header_query:<35}", end="")
    for name in eval_names:
        print(f"{name[:col_w]:>{col_w}}", end="")
    print()
    print("-" * (47 + col_w * len(eval_names)))

    for r in results:
        q_trunc = textwrap.shorten(r["query"], width=33, placeholder="…")
        print(f"{r['row_index']:<4}{r['id']:<8}{q_trunc:<35}", end="")
        for name in eval_names:
            s = r["scores"][name]
            cell = f"{s['score']}{'✓' if s['passed'] else '✗'}"
            print(f"{cell:>{col_w}}", end="")
        print()


def print_comparison(
    v1_summary: dict[str, dict],
    v2_summary: dict[str, dict],
    evaluator_names: list[str],
) -> None:
    print()
    print("=" * 78)
    print("AGGREGATE COMPARISON — V1 vs V2")
    print("=" * 78)
    print(
        f"{'Evaluator':<28}{'V1 Mean':>10}{'V2 Mean':>10}"
        f"{'Delta':>10}{'V1 Pass%':>10}{'V2 Pass%':>10}"
    )
    print("-" * 78)
    for name in evaluator_names:
        v1s, v2s = v1_summary[name], v2_summary[name]
        print(
            f"{name:<28}{v1s['mean_score']:>10.2f}{v2s['mean_score']:>10.2f}"
            f"{(v2s['mean_score'] - v1s['mean_score']):>+10.2f}"
            f"{v1s['pass_rate'] * 100:>9.1f}%{v2s['pass_rate'] * 100:>9.1f}%"
        )


# ── Entry point ───────────────────────────────────────────────────────────────

def main() -> None:
    parser = argparse.ArgumentParser(
        description="Local eval harness — mirrors evaluation_agent_batch_eval_create"
    )
    parser.add_argument("--limit", type=int, help="Only run first N rows (for smoke testing)")
    parser.add_argument(
        "--judge-model", default=os.environ.get("JUDGE_MODEL", "gpt-4o")
    )
    args = parser.parse_args()

    client = get_client()
    model_name = get_model_name()
    dataset = load_dataset()
    if args.limit:
        dataset = dataset[: args.limit]
    evaluators = load_evaluators()
    evaluator_names = [e["name"] for e in evaluators]

    print(f"Dataset rows:  {len(dataset)}")
    print(f"Evaluators:    {evaluator_names}")
    print(f"Judge model:   {args.judge_model}")
    print(f"Agent model:   {model_name}")
    print()

    print("Running V1...")
    os.environ["SYSTEM_PROMPT_PATH"] = str(PROMPTS_DIR / "system_prompt_v1.md")
    v1_def = build_agent_definition()
    v1_results = run_eval(client, v1_def, dataset, evaluators, args.judge_model, "V1")
    v1_summary = aggregate(v1_results, evaluators)
    print_report("V1 (baseline)", v1_results, v1_summary, evaluators)

    print("\nRunning V2...")
    os.environ["SYSTEM_PROMPT_PATH"] = str(PROMPTS_DIR / "system_prompt_v2.md")
    v2_def = build_agent_definition()
    v2_results = run_eval(client, v2_def, dataset, evaluators, args.judge_model, "V2")
    v2_summary = aggregate(v2_results, evaluators)
    print_report("V2 (optimized)", v2_results, v2_summary, evaluators)

    print_comparison(v1_summary, v2_summary, evaluator_names)

    print()
    print(
        textwrap.dedent("""
            How to read this:
              - Fairness & Calibration overall should be markedly higher for V2.
              - The biggest deltas should be in the 'partial', 'sparse', and
                'conflicting' rows. Those are where V1's overconfidence shows up.
              - The 'high' evidence-quality rows should be roughly unchanged.
              - If V1 and V2 are within ~0.2 overall on Fairness, the optimization
                gap is too small for the live demo.
        """).strip()
    )

    # JSON sidecar — mirrors evaluation_agent_batch_eval_create output shape
    output = {
        "v1": {"results": v1_results, "summary": v1_summary},
        "v2": {"results": v2_results, "summary": v2_summary},
    }
    out_path = REPO_ROOT / "eval_results.json"
    out_path.write_text(json.dumps(output, indent=2))
    print(f"\nJSON sidecar written to {out_path}")


if __name__ == "__main__":
    main()
