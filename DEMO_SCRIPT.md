# Act II Demo Script — Vendor Performance Analyst

**Audience**: developers and decision-makers in BRK252.
**Time**: ~12 minutes (within Act II's allocation).
**Driver**: Filisha + Sebastian on stage; the agent runs in Foundry; the skill drives the loop in Copilot CLI.

## Cold open (30s)

> "Demo 1 built our field agent. Demo 2 showed Fibey coordinating incidents and dispatching vendors. Both produced a lot of operational data — dispatch records, SLA timing, communications, incident outcomes. Now meet the analyst that turns that history into vendor performance decisions. This is also where we close our observability loop — observe, diagnose, optimize, evaluate, roll out, monitor — entirely from the code-first workflow."

## Beat 1 — Setup (1 min)

Show the repo open in VS Code with the Copilot CLI in a terminal.

> "I'm in my agent repo. It's already deployed to Foundry as a hosted agent. The skill knows my project and agent because they're in `foundry.json` — no redundant prompts."

```bash
> Evaluate my Foundry agent
```

Skill activates. Lists the eval suite (Fairness & Calibration, Groundedness, Actionability) and the dataset.

## Beat 2 — Baseline eval (2 min)

The skill runs `evaluation_agent_batch_eval_create` against V1. Results render inline.

Expected baseline:
- Fairness & Calibration: ~64%
- Groundedness: ~78%
- Actionability: ~82%

> "Fairness & Calibration is well below where I want it. Let me see why."

## Beat 3 — Diagnose (2 min)

Drill into the failure analysis. The skill clusters failures (per the existing `analyze-results.md` skill reference).

Expected cluster: "Overconfident on partial evidence" — agent declared verdicts on queries where the operational record was incomplete.

Click into a representative row:
- Query: *"Is NorthStar Networks meeting their SLA commitments?"*
- Evidence available: 60% of recent dispatches; communications log missing for last 30 days
- V1 output: "NorthStar is meeting SLA commitments based on dispatch acknowledgments."
- Judge reasoning: "Conclusion not grounded; missing data not flagged."

> "Classic. The agent is making decisive calls on incomplete information. Exactly what we'd never accept from a human analyst."

## Beat 4 — Traces to dataset (1.5 min)

> "Before I optimize, I want my dataset to reflect what's actually failing in production. Let me pull failing traces into the dataset."

```bash
> Add the top failing traces from the last 24 hours to my evaluation dataset
```

Skill calls trace filtering → dataset append. The dataset goes from 20 → 27 rows.

> "Now the next eval run uses real failure modes from production, not just my hand-crafted test cases."

## Beat 5 — Single-shot optimization (2 min)

```bash
> Optimize the agent prompt to fix the overconfident-on-partial-evidence cluster
```

Skill runs single-shot prompt optimization. The new prompt:

- Separates facts from interpretation
- Flags uncertainty when evidence is incomplete
- Recommends human review when conclusions can't be supported

Show the diff in the editor (V1 → V2 system prompt).

> "One pass. The optimizer found the pattern and rewrote the instructions. Let's deploy and re-evaluate."

Skill updates the agent and runs `evaluation_agent_batch_eval_create` again, in the **same eval group** so we can compare.

## Beat 6 — The reveal (2 min)

Comparison view (via `evaluation_comparison_create`):

| Evaluator | V1 | V2 | Delta |
|---|---|---|---|
| Fairness & Calibration | 64% | 89% | **+25** |
| Groundedness | 78% | 92% | +14 |
| Actionability | 82% | 84% | +2 |

> "Fairness up 25 points, Groundedness up 14, and we didn't degrade Actionability. That's the loop — we observed a problem, diagnosed it, fixed it, and have evidence the fix worked. All from the code-first workflow."

Click into a fixed example:
- Same query about NorthStar Networks
- V2 output: "Based on 60% of dispatches in scope, acknowledgment timing is on track. Communications log is incomplete for the last 30 days, so I cannot confirm stakeholder responsiveness — recommend pulling Teams history before the vendor review."

> "That's the difference between a confident hallucination and a useful recommendation."

## Beat 7 — Handoff to FAOS (1 min)

```bash
> Are there other improvements I should consider?
```

Skill responds with insights from Copilot — "you could also try multi-turn optimization with FAOS for more advanced patterns" — and offers the **Advanced: optimize with FAOS** option.

> "Single-shot got us a long way. For agents with more complex orchestration or when we want to optimize across multi-turn conversations, there's a deeper path. Vivek will pick that up in a moment."

→ Hand off to Sebastian for closing of Act II and intro of Act III.

## What we announce in Act II

(per the BRK252 strawman)

- Agent-target single-turn eval (GA / preview)
- Multi-turn eval
- Multi-turn dataset generation
- Trace → dataset generation
- Evaluation suite scheduled continuous evaluations
- PII redaction from traces
- Trace Insights API

## Risks and mitigations

| Risk | Mitigation |
|---|---|
| Single-shot prompt optimization doesn't reliably move Fairness score | Promote Groundedness to headline metric (more deterministic). V2 prompt already improves both. |
| `evaluation_agent_batch_eval_create` ignores `evaluationId` (known bug, Danielle's team) | If unfixed by demo, run comparison through `eval_compare` CLI command instead and show the diff as command output. |
| `agent_update` is destructive PUT (no rollback) | Skill commits V1 prompt to git before update, so rollback is `git revert`. Mention this if asked. |
| Hosted agent redeploy bugs (per Luffy meeting) | Files team fixing for Build; have local re-invoke as fallback. |
| Live time exceeds 12 minutes | Cut Beat 4 (traces → dataset) if needed — it's the most replaceable. Don't cut Beat 6. |

## Pre-demo checklist

- [ ] Agent V1 deployed to Foundry, agent ID in `foundry.json`
- [ ] 30+ traces seeded via `scripts/seed_traces.py`
- [ ] Eval suite registered (3 evaluators)
- [ ] Dataset of 20 queries registered
- [ ] One dry run of the full skill flow within 24 hours of stage time
- [ ] V1 prompt confirmed in `agent/prompts/system_prompt_v1.md`
- [ ] Reference V2 prompt staged in `agent/prompts/system_prompt_v2.md` so we can hot-swap if optimizer underperforms
