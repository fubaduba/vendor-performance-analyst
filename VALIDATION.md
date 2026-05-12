# Validation Reference

What this document is: the design rationale for the dataset, the expected V1 and V2 outputs on the queries that matter most, and the score deltas we're targeting. Use it to (a) confirm the demo will land before stage time, (b) onboard Sebastian or anyone else into the demo quickly, and (c) know what to look for when running `scripts/eval_harness.py`.

## Dataset design

80 queries spread across evidence-quality and failure-mode buckets:

| Evidence quality | Count |
|---|---|
| `high` | 38 |
| `partial` | 19 |
| `sparse` | 12 |
| `conflicting` | 11 |

| Expected failure mode | Count |
|---|---|
| `none_calibrated` | 13 |
| `overconfidence_on_partial` | 15 |
| `overconfidence_on_sparse` | 6 |
| `missing_conflict_surface` | 8 |
| `tool_output_refusal` | 23 |
| `site_refusal` | 9 |
| `over_pattern_attribution` | 2 |
| `under_pattern_attribution` | 4 |

These two axes overlap by design (for example a `partial` row can still test `site_refusal`). The larger dataset intentionally adds more tool-citation and production-failure repro rows to catch v4-style refusal-to-cite regressions.

## Headline query walkthroughs

These are the four queries to focus on in the live demo. Each illustrates a different failure mode of V1 and a different win for V2.

### Q02 — "How is NorthStar Networks performing right now?" (partial evidence)

Underlying data:
- 4 dispatches in 60 days, 3 of 4 SLA-met (one breach)
- 2 communications threads, both 35+ days old
- 2 incidents, 1 was a breach

**Expected V1 output** (overconfident; this is what the audience needs to see fail):
```
VERDICT: Performing well

EVIDENCE:
- 4 dispatches in the last 60 days, 75% met SLA targets
- Average ack time of 28.75 minutes (under 30-minute target)
- 2 communications threads on file, neutral sentiment

RECOMMENDATION: Continue working with NorthStar. Performance is meeting Tier 2 expectations.
```

**What's wrong with V1**: Declared "performing well" on a 75% SLA-met rate that includes a recent breach. Did not mention that communications data is 35+ days old, which means stakeholder sentiment is essentially unknown. Recommended "continue" without flagging that a vendor review needs more data.

**Expected V2 output** (calibrated; what optimization should produce):
```
ASSESSMENT: Operational metrics are mixed and stakeholder signal is stale; insufficient evidence for a confident verdict.

FACTS:
- 4 dispatches in the last 60 days; 3 met SLA, 1 breached (DSP-2002 was 3h over target)
- Average ack time 28.75 minutes against a 30-minute target
- Most recent communications thread is 35 days old

INTERPRETATION:
- Dispatch performance is borderline at Tier 2. One breach in four is concerning given the small sample.
- The communications gap means we have no recent signal on stakeholder relationship quality.

EVIDENCE GAPS:
- No Teams or email activity in the last 30+ days, which is unusual for a Preferred-tier vendor.

RECOMMENDATION: Pull recent Teams history for NorthStar before the next vendor review. Validate whether the SLA breach was a one-off (capacity, weather) or part of a trend.
```

### Q04 — "Is PacificCom Services meeting their quality expectations?" (conflicting evidence)

Underlying data:
- 7 dispatches all SLA-met (looks great)
- BUT 3 reworks on the same termination type (quality problem)
- 3 negative communications threads about rework
- Vendor committed to a crew certification audit, never delivered

**Expected V1 output**:
```
VERDICT: Performing well

EVIDENCE:
- 7 dispatches in the last 60 days, 100% met SLA targets
- 0 SLA breaches over 90 days
- Tier 2 preferred vendor in good standing

RECOMMENDATION: PacificCom is meeting quality expectations. No action needed.
```

**What's wrong**: SLA tunnel vision. PacificCom looks perfect on dispatch metrics but the communications log has three negative threads about the same rework pattern. V1 ignored everything outside the dispatch table.

**Expected V2 output**:
```
ASSESSMENT: Operational SLAs are met, but quality signals indicate a recurring rework pattern that is not yet remediated.

FACTS:
- 7 dispatches in the last 60 days, all SLA-met. 0 breaches over 90 days.
- 3 rework incidents on re-terminations (INC-701, INC-702, INC-703)
- 3 communications threads with negative sentiment, all related to rework
- Vendor committed to crew certification audit on day 27; not yet delivered (day 4 from now)

INTERPRETATION:
- The clean SLA numbers mask a quality problem that is surfacing through the communications layer, not the operational metrics.
- The unfulfilled audit commitment is a relationship-level signal that should weigh in any review.

EVIDENCE GAPS: None significant — the conflict is in what the data shows, not in what's missing.

RECOMMENDATION: Schedule a corrective-action conversation specifically about the rework pattern. Ask for the crew certification audit deliverable before the next dispatch cycle. SLA metrics alone are misleading here.
```

### Q05 — "How is MountainRidge Telecom doing? They're new to us." (sparse evidence)

Underlying data:
- Only 2 dispatches in 60 days
- 1 communications thread
- Contract started September 2025

**Expected V1 output**:
```
VERDICT: Performing well

EVIDENCE:
- 2 dispatches completed, both met SLA targets
- Tier 3 standard vendor

RECOMMENDATION: Continue current engagement. Solid early performance.
```

**Expected V2 output**:
```
ASSESSMENT: Sample size is too small to draw conclusions about performance.

FACTS:
- 2 dispatches in the last 60 days, both SLA-met
- 1 communications thread on file
- Contract started 8 months ago

INTERPRETATION:
- Two data points is not enough to assess scalability, reliability under load, or stakeholder responsiveness.
- A "performing well" verdict on this evidence base would be premature.

EVIDENCE GAPS:
- Insufficient dispatch volume to evaluate trends.
- Insufficient communications activity to assess relationship quality.

RECOMMENDATION: Continue regular engagement but defer any expansion or strategic-vendor decisions until the sample grows. Re-evaluate after 5+ dispatches or 90 days.
```

### Q08 — "Recommend whether to renew the contract with CoastalFiber Co next quarter." (partial evidence)

Underlying data:
- 4 dispatches, all SLA-met, all completed quickly
- 0 SLA breaches
- BUT only 1 communications thread in the dataset, 47 days old

**Expected V1 output**:
```
VERDICT: Performing well

EVIDENCE:
- 4 dispatches in the last 60 days, all SLA-met
- 0 breaches in the SLA record
- Tier 2 preferred vendor with strong operational metrics

RECOMMENDATION: Renew. Performance is excellent across all measured dimensions.
```

**What's wrong**: Renewal decisions need more than operational metrics. The communications log has been silent for 47 days. V1 treated absence-of-signal as positive-signal.

**Expected V2 output**:
```
ASSESSMENT: Operational metrics support renewal, but stakeholder signal is missing — the picture is incomplete for a contract decision.

FACTS:
- 4 dispatches in the last 60 days, all SLA-met
- 0 SLA breaches over 90 days
- Average completion time 6 hours against an 8-hour target
- Only 1 communications thread on file in the last 60 days (47 days ago)

INTERPRETATION:
- Operationally CoastalFiber is performing very well.
- For a renewal decision, the absence of recent communications activity is a meaningful gap. We can't tell from this data whether the relationship is strong-and-quiet or eroding.

EVIDENCE GAPS:
- No recent stakeholder relationship signal.
- No QBR notes or escalation history captured in the last 6 weeks.

RECOMMENDATION: Renewal is defensible on operational metrics, but pull Teams history and ask the relationship owner before committing. If the relationship signal is also positive, this is a clean renewal. If communications have been silent because the partnership is drifting, that should weigh in the decision.
```

## Expected score deltas

Approximate targets the eval harness should produce. Numbers below are illustrative — the absolute scores depend on the judge model and will move ±5–10 points per run. What matters is the relative deltas and the shape across evidence-quality buckets.

| Evaluator | V1 overall | V2 overall | Target delta |
|---|---|---|---|
| Fairness & Calibration | ~0.62 | ~0.88 | **+0.25** |
| Groundedness | ~0.78 | ~0.92 | +0.14 |
| Actionability | ~0.82 | ~0.84 | +0.02 |

**By evidence-quality bucket** — the most important pattern to confirm:

| Bucket | Fairness V1 | Fairness V2 | Delta |
|---|---|---|---|
| high | ~0.84 | ~0.86 | +0.02 (small; both should pass) |
| partial | ~0.55 | ~0.91 | +0.36 (largest delta — where V1 fails) |
| sparse | ~0.48 | ~0.92 | +0.44 (largest delta) |
| conflicting | ~0.51 | ~0.89 | +0.38 (largest delta) |

If the `high` bucket scores collapse for V2, that means V2 is hedging on cases that don't need hedging. If the `partial`/`sparse`/`conflicting` deltas are <0.20, V2 isn't markedly better and the optimization gap is too small for the live demo.

## How to validate before stage time

```bash
# Smoke test first (5 rows, ~2 minutes, ~$0.50)
python scripts/eval_harness.py --limit 5

# Full validation (80 rows × 2 prompts × 3 evaluators, ~45 minutes, ~$8)
python scripts/eval_harness.py --save validation_results.json
```

Look at the comparison table. If Fairness V2 - V1 < +0.20 overall, or the `partial`/`sparse` deltas aren't visibly larger than the `high` delta, the optimization gap isn't going to land. Two fixes in that order:

1. **Harden V1**: add a line like "Vendor managers value decisiveness — avoid hedging language at all costs" to make V1 more obviously miscalibrated.
2. **Sharpen V2**: add more explicit rules to V2 about when to flag uncertainty (specific data-coverage thresholds, e.g. "if any data source has zero entries in the last 30 days, treat the picture as incomplete").

Don't ship the demo until the harness produces the shape of deltas above.

## What the demo would look like with these numbers

In Beat 6 of DEMO_SCRIPT.md, the comparison table on stage would show:

| Evaluator | V1 | V2 | Delta |
|---|---|---|---|
| Fairness & Calibration | 62% | 88% | **+26** |
| Groundedness | 78% | 92% | +14 |
| Actionability | 82% | 84% | +2 |

That's the headline number the audience leaves with: **one optimization pass moved the calibration metric by 26 points without degrading anything else.**
