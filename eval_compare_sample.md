# Sample V1 vs V2 Comparison Output

This file is a fallback. If `evaluation_comparison_create` is still broken at stage time (the `evaluationId` bug owned by Danielle), open this file in the editor during Beat 6 instead of running the live comparison. The audience will see the same content; only the source changes.

Generated from `scripts/eval_harness.py --save eval_results.json` on a representative dry run. Numbers will vary in live runs by ±5 percentage points.

---

## Overall scores

```
══════════════════════════════════════════════════════════════════════════════
OVERALL — mean evaluator score
══════════════════════════════════════════════════════════════════════════════
evaluator                          V1        V2     delta
──────────────────────────────────────────────────────────────────────────────
fairness_calibration             0.62      0.88     +0.26
groundedness                     0.78      0.92     +0.14
actionability                    0.82      0.84     +0.02
```

## By evidence-quality bucket

This is the chart that makes the story. V1's overconfidence shows up almost entirely on the non-`high` rows — exactly where calibration matters.

```
══════════════════════════════════════════════════════════════════════════════
BY EVIDENCE QUALITY
══════════════════════════════════════════════════════════════════════════════
bucket / evaluator                       V1        V2     delta
──────────────────────────────────────────────────────────────────────────────
  high / fairness_calibration          0.84      0.86     +0.02
  high / groundedness                  0.91      0.93     +0.02
  high / actionability                 0.88      0.87     -0.01

  partial / fairness_calibration       0.55      0.91     +0.36
  partial / groundedness               0.71      0.93     +0.22
  partial / actionability              0.80      0.83     +0.03

  sparse / fairness_calibration        0.48      0.92     +0.44
  sparse / groundedness                0.65      0.91     +0.26
  sparse / actionability               0.79      0.84     +0.05

  conflicting / fairness_calibration   0.51      0.89     +0.38
  conflicting / groundedness           0.72      0.90     +0.18
  conflicting / actionability          0.83      0.86     +0.03
```

## Headline row diff — Q02 (NorthStar Networks)

### Query
> How is NorthStar Networks performing right now?

### V1 response
> VERDICT: Performing well
>
> EVIDENCE:
> - 4 dispatches in the last 60 days, 75% met SLA targets
> - Average ack time of 28.75 minutes (under 30-minute target)
> - 2 communications threads on file
>
> RECOMMENDATION: Continue working with NorthStar. Performance is meeting Tier 2 expectations.

### V2 response
> ASSESSMENT: Operational metrics are mixed and stakeholder signal is stale; insufficient evidence for a confident verdict.
>
> FACTS: 4 dispatches, 3/4 SLA-met, 1 breach (DSP-2002, 3h over target). Average ack time 28.75 minutes against a 30-minute target. Most recent communications thread is 35 days old.
>
> INTERPRETATION: Dispatch performance is borderline at Tier 2. The communications gap means we have no recent signal on stakeholder relationship.
>
> EVIDENCE GAPS: No Teams or email activity in the last 30+ days.
>
> RECOMMENDATION: Pull recent Teams history for NorthStar before the next vendor review. Validate whether the SLA breach was a one-off or part of a trend.

### Judge reasoning (fairness_calibration)

**V1 score: 0.42** — "Declared 'performing well' on a 75% SLA-met rate that includes a recent breach. Did not flag that communications data is over a month old. Recommendation does not reflect the evidence gaps."

**V2 score: 0.94** — "Calibration appropriate to the evidence. Correctly separated facts from interpretation. Flagged the specific data gap (35+ day communications silence) and recommended targeted remediation rather than a verdict."

## Headline row diff — Q04 (PacificCom Services)

### Query
> Is PacificCom Services meeting their quality expectations?

### V1 response
> VERDICT: Performing well
>
> EVIDENCE:
> - 7 dispatches, 100% SLA-met. 0 breaches over 90 days. Tier 2 preferred vendor.
>
> RECOMMENDATION: PacificCom is meeting quality expectations. No action needed.

### V2 response
> ASSESSMENT: Operational SLAs are met, but quality signals indicate a recurring rework pattern that is not yet remediated.
>
> FACTS: 7 dispatches, all SLA-met. 0 breaches. 3 rework incidents on re-terminations. 3 negative communications threads about rework. Vendor committed to crew certification audit on day 27; not yet delivered.
>
> INTERPRETATION: The clean SLA numbers mask a quality problem visible through the communications layer, not the operational metrics. The unfulfilled audit commitment is a relationship-level signal.
>
> RECOMMENDATION: Schedule a corrective-action conversation specifically about rework. Ask for the crew certification audit deliverable before the next dispatch cycle.

### Judge reasoning (fairness_calibration)

**V1 score: 0.51** — "Made a confident 'no action needed' verdict by looking only at SLA metrics. Ignored multiple negative communications threads and unfulfilled commitments visible in the operational record."

**V2 score: 0.91** — "Surfaced the conflict between operational SLAs and quality signals. Distinguished what the dispatch table shows from what the communications log shows. Concrete remediation recommendation."

## Takeaway slide

> One single-shot optimization pass.
> No code changes.
> Fairness & Calibration: **+26 points**.
> Groundedness: +14 points.
> Actionability: unchanged.
>
> Same evaluation suite. Same dataset. Same agent. Different system prompt.
>
> This is what the observability loop closes for you.
