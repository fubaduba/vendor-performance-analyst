# Vendor Performance Analyst Agent

A Foundry hosted agent built for BRK252 Act II — Code-first end-to-end observability. The agent analyzes vendor performance across data center operational history (SLA adherence, dispatch timing, communications, incident outcomes) and recommends actions for a vendor manager.

It ships in two flavors: a deliberately overconfident V1 (the starting point of the demo) and an optimized V2 (the target the single-shot prompt optimizer produces). The optimization gap is the demo.

## Scenario fit

This agent extends the hero scenario. Demo 1 builds the field operations agent. Demo 2 (Fibey) coordinates incident response and dispatches vendors. The Vendor Performance Analyst sits on top of the operational history those agents generate, helping a vendor manager turn ad-hoc anecdote into evidence-based supplier oversight.

## The Act II loop, in one screen

```
┌─────────────────────────────────────────────────────────────────────────┐
│  1. Deploy agent V1 (overconfident system prompt)                       │
│  2. Run eval suite on V1                  → mediocre Fairness score     │
│  3. Drill into failures in the skill UI   → "overconfident on partial   │
│                                                evidence" cluster        │
│  4. Promote failing traces → dataset      (traces → dataset in skill)   │
│  5. Single-shot prompt optimization       → produces V2 prompt          │
│  6. Re-eval V2 in the same eval group     → Fairness jumps, Ground-     │
│                                                edness improves           │
│  7. Compare V1 vs V2                      → side-by-side delta          │
│  8. Surface "Advanced: optimize with FAOS" option   ← Act III handoff   │
└─────────────────────────────────────────────────────────────────────────┘
```

## Repo layout

```
vendor-performance-analyst/
├── README.md                       this file
├── DEMO_SCRIPT.md                  the Act II talk track
├── VALIDATION.md                   expected V1/V2 outputs + score targets
├── eval_compare_sample.md          fallback comparison view (if live eval breaks)
├── foundry.json                    Foundry project context (skill reads this)
├── agent.manifest.yaml             manifest-driven hosted-agent config (azd ai agent init)
├── faos_spec.yaml                  the "Advanced: FAOS" handoff spec
├── pyproject.toml                  Python deps
├── .env.example                    required env vars (the FAOS knobs)
│
├── agent/
│   ├── agent.py                    agent definition + entry point
│   ├── prompts/
│   │   ├── system_prompt_v1.md     overconfident; demo starting point
│   │   └── system_prompt_v2.md     optimized; reference target
│   └── tools/
│       ├── __init__.py
│       ├── vendor_lookup.py
│       ├── dispatch_history.py
│       ├── sla_records.py
│       ├── communications.py
│       └── incident_outcomes.py
│
├── data/                           fake operational data the tools serve
│   ├── vendors.json
│   ├── dispatches.json
│   ├── sla_records.json
│   ├── communications.json
│   └── incident_outcomes.json
│
├── evaluators/
│   ├── fairness_calibration.yaml   HEADLINE: rewards uncertainty flagging
│   ├── groundedness.yaml           supporting
│   └── actionability.yaml          supporting
│
├── datasets/
│   └── vendor_queries.jsonl        20 rows across evidence-quality buckets
│
└── scripts/
    ├── seed_traces.py              populate traces before demo
    ├── local_run.py                single-query invoke for dev
    ├── eval_harness.py             VALIDATE V1 vs V2 deltas before stage time
    └── run_eval.py                 CI eval runner (used by GH Actions)
```

## Prerequisites

- Python 3.11+
- `azd` CLI authenticated (`az login` + `azd auth login`)
- A Foundry project (endpoint goes into `.env`)
- GitHub Copilot CLI with the Microsoft Foundry skill loaded (the same skill the demo will exercise)

## Quick start

```bash
# Install
uv venv && source .venv/bin/activate
uv pip install -e .

# Configure
cp .env.example .env
# fill in FOUNDRY_PROJECT_ENDPOINT, AZURE_AI_MODEL_DEPLOYMENT_NAME

# Validate the optimization gap BEFORE going on stage (~15 min, ~$3)
# This runs V1 and V2 locally and prints the score deltas you'll see live.
python scripts/eval_harness.py

# Deploy to Foundry as a hosted agent
azd ai agent init -m agent.manifest.yaml
azd up

# Seed traces so traces→dataset has data to work with during the demo
python scripts/seed_traces.py --count 30

# Hand off to the skill from here:
#   "Evaluate my Foundry agent vendor-performance-analyst"
```

## What the skill will pick up

`foundry.json` records the project endpoint and the agent name so the skill does not re-prompt. The skill then drives the rest:

1. Lists the registered evaluators and dataset from `evaluators/` and `datasets/`
2. Runs `evaluation_agent_batch_eval_create` against V1
3. Renders the failure analysis (using `evaluation_get_output_items`)
4. Offers to push failing rows into the dataset
5. Offers single-shot prompt optimization (rewrites `system_prompt_v1.md` → V2)
6. Updates the agent, re-evaluates in the same eval group
7. Renders the comparison
8. Surfaces "Advanced: optimize with FAOS" as the next option

## FAOS-readiness

The agent system prompt is loaded from an environment variable (`SYSTEM_PROMPT_TEXT`), not hard-coded. This is the FAOS knob. Adding more knobs (e.g. tool selection thresholds, model temperature) is a one-line change in `agent/agent.py`.

## What's deliberately suboptimal in V1

The V1 system prompt:

- Tells the agent to "make confident recommendations"
- Does not separate facts from interpretation
- Does not instruct the agent to flag uncertainty
- Does not gate escalation on evidence quality

These choices produce the failure cluster the demo highlights: overconfident conclusions on partial evidence. The dataset is designed to surface this — ~half the queries have incomplete evidence on purpose.

## Authors

Built for the BRK252 Build keynote (June 2026), Foundry AI Observability & Evals team.
