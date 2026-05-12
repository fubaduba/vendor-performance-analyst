"""Run the eval suite against the deployed agent (used by CI).

Mirrors what the skill does at demo time, but headless so it can run in GitHub
Actions. Writes eval_summary.md (consumed by the PR comment step) and exits
nonzero if --fail-on-regression is set and any evaluator fell below its pass
threshold.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

import yaml

sys.path.insert(0, str(Path(__file__).parent.parent))

from agent.agent import get_project_client  # noqa: E402

REPO_ROOT = Path(__file__).parent.parent


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--fail-on-regression", action="store_true")
    args = parser.parse_args()

    foundry_json = json.loads((REPO_ROOT / "foundry.json").read_text())
    agent_id = foundry_json["agent_id"]
    dataset_name = foundry_json["default_dataset"]
    evaluator_names = foundry_json["default_evaluators"]

    project_client = get_project_client()
    print(f"Running eval: agent={agent_id} dataset={dataset_name} evaluators={evaluator_names}")

    run = project_client.evaluations.create_batch_eval(
        agent_id=agent_id,
        dataset_name=dataset_name,
        evaluator_names=evaluator_names,
    )
    print(f"Eval run started: {run.id}")
    run = project_client.evaluations.wait_for_completion(run.id, timeout=900)
    print(f"Status: {run.status}")

    thresholds = {}
    for path in (REPO_ROOT / "evaluators").glob("*.yaml"):
        config = yaml.safe_load(path.read_text())
        thresholds[config["name"]] = config.get("threshold", {})

    summary_lines = ["# Eval Summary", "", f"Run ID: `{run.id}`", "", "| Evaluator | Score | Threshold | Status |", "|---|---|---|---|"]
    failed = False
    for name in evaluator_names:
        score = run.scores.get(name, 0.0)
        pass_threshold = thresholds.get(name, {}).get("pass", 0.7)
        ok = score >= pass_threshold
        status = "✅" if ok else "❌"
        if not ok:
            failed = True
        summary_lines.append(f"| {name} | {score:.3f} | {pass_threshold:.2f} | {status} |")

    summary_path = REPO_ROOT / "eval_summary.md"
    summary_path.write_text("\n".join(summary_lines))
    print(f"Wrote {summary_path}")

    if failed and args.fail_on_regression:
        print("One or more evaluators fell below threshold.")
        sys.exit(1)


if __name__ == "__main__":
    main()
