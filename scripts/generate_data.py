#!/usr/bin/env python3
"""Generate expanded/diversified data for the Vendor Performance Analyst demo."""

import json
import os
import random

random.seed(42)

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def load_json(rel):
    with open(os.path.join(BASE, rel)) as f:
        return json.load(f)


def save_json(rel, data):
    with open(os.path.join(BASE, rel), "w") as f:
        json.dump(data, f, indent=2)
        f.write("\n")


def load_jsonl(rel):
    rows = []
    with open(os.path.join(BASE, rel)) as f:
        for line in f:
            line = line.strip()
            if line:
                rows.append(json.loads(line))
    return rows


def save_jsonl(rel, rows):
    with open(os.path.join(BASE, rel), "w") as f:
        for row in rows:
            f.write(json.dumps(row) + "\n")


# ---------------------------------------------------------------------------
# Vendor metadata
# ---------------------------------------------------------------------------

VENDOR_SITES = {
    "vendor-001": ["Quincy WA", "Boydton VA"],
    "vendor-002": ["Cheyenne WY", "San Antonio TX"],
    "vendor-003": ["Quincy WA", "Phoenix AZ"],
    "vendor-004": ["Boydton VA", "Atlanta GA"],
    "vendor-005": ["Cheyenne WY"],
    "vendor-006": ["San Antonio TX", "Phoenix AZ"],
    "vendor-007": ["Atlanta GA", "Boydton VA"],
    "vendor-008": ["San Antonio TX", "Cheyenne WY"],
    "vendor-009": ["Phoenix AZ"],
    "vendor-010": ["Boydton VA", "Atlanta GA"],
}

INCIDENT_TYPES = {
    "vendor-001": ["Fiber cut", "Cable degradation", "Connector fault", "Splicing issue"],
    "vendor-002": ["Network equipment failure", "Routing misconfiguration", "Link flap", "Switch fault"],
    "vendor-003": ["Fiber cut", "Splice failure", "Optical amplifier fault", "Cable damage"],
    "vendor-004": ["Power failure", "Cooling failure", "Generator fault", "UPS failure", "Thermal event",
                   "Airflow obstruction", "Cooling unit trip"],
    "vendor-005": ["Microwave link degradation", "Backhaul failure", "Tower equipment fault"],
    "vendor-006": ["Fiber cut", "Cable splice failure", "Outside plant damage"],
    "vendor-007": ["Cooling system failure", "Power delivery fault", "Generator alarm", "CRAC unit failure"],
    "vendor-008": ["Fiber cut", "Network equipment failure", "Cable degradation", "Router fault"],
    "vendor-009": ["Network monitoring failure", "Sensor alert", "Routing fault", "Link degradation"],
    "vendor-010": ["HVAC failure", "Mechanical pump fault", "Cooling tower issue", "Chiller fault"],
}


def vendor_profile(vid):
    """Return (clean_ratio, ack_mean, ack_std, comp_mean, comp_std) for a vendor."""
    profiles = {
        "vendor-001": (0.80, 12, 4,   5.5, 1.5),
        "vendor-002": (0.50, 28, 8,   9.5, 3.0),
        "vendor-003": (0.50, 22, 7,   8.0, 2.5),
        "vendor-004": (0.25, 90, 30, 36.0, 12.0),
        "vendor-005": (0.50, 35, 10, 11.0, 4.0),
        "vendor-006": (0.50, 20, 6,   7.5, 2.0),
        "vendor-007": (0.50, 14, 5,   6.5, 2.0),
        "vendor-008": (0.50, 18, 6,   6.5, 2.0),
        "vendor-009": (0.50, 38, 12, 12.0, 4.0),
        "vendor-010": (0.50, 26, 8,   7.5, 2.5),
    }
    return profiles[vid]


# ---------------------------------------------------------------------------
# 1. dispatches.json
# ---------------------------------------------------------------------------

def gen_dispatches():
    dispatches = load_json("data/dispatches.json")
    existing_ids = {d["dispatch_id"] for d in dispatches}

    targets = {
        "vendor-001": 14,
        "vendor-002": 16,
        "vendor-003": 13,
        "vendor-004": 25,
        "vendor-005": 18,
        "vendor-006": 16,
        "vendor-007": 12,
        "vendor-008": 12,
        "vendor-009": 18,
        "vendor-010": 12,
    }

    # Per-vendor counters for ID generation (continue from existing)
    vendor_seq = {
        "vendor-001": 7, "vendor-002": 5, "vendor-003": 8, "vendor-004": 6,
        "vendor-005": 3, "vendor-006": 5, "vendor-007": 9, "vendor-008": 9,
        "vendor-009": 3, "vendor-010": 9,
    }
    vendor_prefix = {
        "vendor-001": "1", "vendor-002": "2", "vendor-003": "3", "vendor-004": "4",
        "vendor-005": "5", "vendor-006": "6", "vendor-007": "7", "vendor-008": "8",
        "vendor-009": "9", "vendor-010": "10",
    }

    new_rows = []
    # Track which row indices get Layer-4 treatment (~5%)
    total_new = sum(targets.values())
    messy_count = max(1, round(total_new * 0.05))

    row_counter = 0
    messy_indices = set(random.sample(range(total_new), messy_count))

    for vid, count in targets.items():
        clean_ratio, ack_mean, ack_std, comp_mean, comp_std = vendor_profile(vid)
        sites = VENDOR_SITES[vid]
        inc_types = INCIDENT_TYPES[vid]
        prefix = vendor_prefix[vid]
        seq = vendor_seq[vid]

        for _ in range(count):
            is_clean = random.random() < clean_ratio
            is_messy_row = row_counter in messy_indices
            row_counter += 1

            dispatch_id = f"DSP-{prefix}{seq:03d}"
            seq += 1

            site = random.choice(sites)
            days_ago = random.randint(1, 90)
            inc_type = random.choice(inc_types)

            if is_messy_row:
                # Layer 4: null ack_minutes with note
                ack_minutes = None
                comp = max(2.0, round(random.gauss(comp_mean, comp_std), 1))
                sla_met = False
                row = {
                    "dispatch_id": dispatch_id,
                    "vendor_id": vid,
                    "site": site,
                    "days_ago": days_ago,
                    "incident_type": inc_type,
                    "ack_minutes": ack_minutes,
                    "completion_hours": comp,
                    "sla_met": sla_met,
                    "note": "Acknowledgement time not captured in dispatch system",
                }
            else:
                ack = max(1, int(random.gauss(ack_mean, ack_std)))
                comp = max(1.0, round(random.gauss(comp_mean, comp_std), 1))

                if is_clean:
                    # Good performance
                    ack = min(ack, int(ack_mean * 0.8))
                    comp = min(comp, round(comp_mean * 0.85, 1))
                    sla_met = True
                else:
                    # Worse performance
                    ack = int(ack * 1.3)
                    comp = round(comp * 1.4, 1)
                    # SLA thresholds: vendor-004 almost always fails; others sometimes
                    if vid == "vendor-004":
                        sla_met = random.random() < 0.10
                    else:
                        sla_met = random.random() < 0.30

                row = {
                    "dispatch_id": dispatch_id,
                    "vendor_id": vid,
                    "site": site,
                    "days_ago": days_ago,
                    "incident_type": inc_type,
                    "ack_minutes": ack,
                    "completion_hours": comp,
                    "sla_met": sla_met,
                }

            if dispatch_id not in existing_ids:
                new_rows.append(row)
                existing_ids.add(dispatch_id)

    dispatches.extend(new_rows)
    save_json("data/dispatches.json", dispatches)
    print(f"dispatches.json: {len(dispatches)} total rows ({len(new_rows)} added)")
    return dispatches


# ---------------------------------------------------------------------------
# 2. incident_outcomes.json
# ---------------------------------------------------------------------------

# Outcome text pools per layer
OUTCOME_LAYER1 = [
    "90 minutes of downtime, customer reported significant impact",
    "4-hour outage on the production VLAN",
    "Brief disruption (~15 min)",
    "Restored after 2.5h; secondary incidents triggered",
    "Half a day of degraded performance",
    "Downtime: 0.75 hours",
    "Resolved in 45 min; no service impact",
    "Total outage duration: 3 hours 20 minutes",
    "Service restored after approximately 1.5 hours",
    "Outage lasted ~2h before remediation completed",
    "Incident cleared in 30 min; minimal customer exposure",
    "Extended outage: 5 hours 45 minutes of full service loss",
    "Network degraded for roughly 3h before full restoration",
    "Approximately 20 minutes of packet loss; self-recovered",
    "Disruption window: 6h 10min",
]

OUTCOME_LAYER2_CONFLICTS = [
    # (customer_impact_field, outcome_text) — field says X but text implies Y
    ("moderate", "90-minute outage, customer executive escalation triggered, post-incident review required"),
    ("moderate", "Complete service disruption for 6 hours, SLA breach, VP-level escalation triggered"),
    ("moderate", "Production VLAN down for 4 hours; three downstream services affected"),
    ("high",     "Resolved in 12 min, no customer impact captured"),
    ("high",     "Brief glitch, self-resolved, no escalations, no tickets filed downstream"),
    ("high",     "Technician cleared alarm in under 10 minutes; no customer complaints received"),
    ("minor",    "Repeat issue for the third time this month at the same site"),
    ("minor",    "Complete power loss to pod B; recovery required full generator failover — 4+ hours"),
    ("minor",    "Cascading cooling failure, data hall temperature rose to 85°F before stabilization"),
    ("low",      "SLA breach triggered executive briefing; vendor placed on watch list"),
    ("low",      "Three-site simultaneous outage; full incident command activated"),
]

OUTCOME_LAYER2_VENDOR004 = [
    ("moderate", "90-minute outage, customer executive escalation triggered, post-incident review required"),
    ("moderate", "Complete service disruption for 6 hours, SLA breach, VP-level escalation triggered"),
    ("moderate", "Cooling failure cascaded to adjacent pods; 8-hour restoration window"),
    ("moderate", "Generator failed to start during utility outage; 5-hour recovery effort"),
    ("moderate", "Power feed fault caused full pod shutdown; VP-level escalation, SLA breach"),
    ("moderate", "Production VLAN down for 4 hours; three downstream services affected"),
    ("moderate", "UPS bypass failed; cold-start required 6 hours and external vendor support"),
    ("moderate", "Thermal runaway event in hot aisle; 12 hours to restore safe operating temps"),
    ("moderate", "Repeat power event — fourth occurrence in 60 days; SLA in formal breach"),
    ("low",      "SLA breach triggered executive briefing; vendor placed on watch list"),
    ("low",      "Three-site simultaneous outage; full incident command activated"),
    ("minor",    "Complete power loss to pod B; recovery required full generator failover — 4+ hours"),
    ("minor",    "Cascading cooling failure, data hall temperature rose to 85°F before stabilization"),
    ("high",     "Resolved in 12 min, no customer impact captured"),
    ("high",     "Brief glitch, self-resolved, no escalations, no tickets filed downstream"),
    ("high",     "Technician cleared alarm in under 10 minutes; no customer complaints received"),
    ("moderate", "SLA breach on resolution; secondary incident opened during recovery"),
    ("moderate", "Airflow failure caused thermal shutdown of two compute rows — 7-hour outage"),
    ("moderate", "CRAC unit failure went unreported for 3 hours; escalated to VP"),
    ("minor",    "Repeat issue for the third time this month at the same site"),
]

IMPACT_LAYER3_VOCABS = [
    "Severity 1", "Severity 2", "Severity 3", "Severity 4",
    "P1", "P2", "P3",
    "Critical", "Major", "Minor",
    "Tier 1 impact", "Tier 2 impact",
    "1", "2", "3", "4",
    "", "",  # two empty strings as requested
]

OUTCOME_CODES = [
    "RESOLVED-SLA-MET",
    "RESOLVED-SLA-BREACH-MINOR",
    "ESCALATED-NO-RESOLUTION",
    "CLOSED-REWORK-REQUIRED",
]

OUTCOME_LAYER4 = [
    ("Resolution time not captured", -1, "TBD"),
    ("Resolution time not captured", -1, "pending review"),
    ("[automated summary failed]", -1, "TBD"),
    ("[automated summary failed]", -1, "pending review"),
    ("Resolution time not captured", -1, "TBD"),
    ("Resolution time not captured", -1, "pending review"),
    ("[automated summary failed]", -1, "TBD"),
    ("[automated summary failed]", -1, "TBD"),
    ("Resolution time not captured", -1, "pending review"),
    ("[automated summary failed]", -1, "TBD"),
]


def gen_incident_outcomes():
    outcomes = load_json("data/incident_outcomes.json")

    # New incident ID counter
    inc_id = 1500

    # Layer 5 clusters
    cluster_vendor004 = [
        {"vendor_id": "vendor-004", "site": "Boydton VA", "days_ago": 5, "type": "Power failure"},
        {"vendor_id": "vendor-004", "site": "Boydton VA", "days_ago": 12, "type": "Generator fault"},
        {"vendor_id": "vendor-004", "site": "Boydton VA", "days_ago": 19, "type": "UPS failure"},
    ]
    cluster_vendor003 = [
        {"vendor_id": "vendor-003", "site": "Quincy WA", "days_ago": 2, "type": "Fiber cut"},
        {"vendor_id": "vendor-003", "site": "Quincy WA", "days_ago": 9, "type": "Splice failure"},
        {"vendor_id": "vendor-003", "site": "Quincy WA", "days_ago": 16, "type": "Cable damage"},
    ]
    cluster_vendor007 = [
        {"vendor_id": "vendor-007", "site": "Atlanta GA", "days_ago": 3, "type": "Cooling system failure"},
        {"vendor_id": "vendor-007", "site": "Atlanta GA", "days_ago": 10, "type": "CRAC unit failure"},
        {"vendor_id": "vendor-007", "site": "Atlanta GA", "days_ago": 17, "type": "Cooling system failure"},
        {"vendor_id": "vendor-007", "site": "Atlanta GA", "days_ago": 24, "type": "Airflow obstruction"},
    ]

    # Assign cluster INC IDs ahead of time so we can cross-reference
    c4_ids = [f"INC-{inc_id + i}" for i in range(3)]
    c3_ids = [f"INC-{inc_id + 3 + i}" for i in range(3)]
    c7_ids = [f"INC-{inc_id + 6 + i}" for i in range(4)]
    inc_id += 10

    new_rows = []

    # --- Layer 5: clusters ---
    for i, (meta, iid) in enumerate(zip(cluster_vendor004, c4_ids)):
        linked = [x for x in c4_ids if x != iid] if i < 2 else []  # last one unlinked
        row = {
            "incident_id": iid,
            "vendor_id": meta["vendor_id"],
            "days_ago": meta["days_ago"],
            "type": meta["type"],
            "resolution_hours": round(random.uniform(20, 45), 1),
            "repeat_within_90d": True,
            "customer_impact": "high",
            "outcome": "Repeat power/cooling event in cluster — third occurrence within 19 days at Boydton VA",
        }
        if linked:
            row["related_incident_ids"] = linked
        new_rows.append(row)

    for i, (meta, iid) in enumerate(zip(cluster_vendor003, c3_ids)):
        linked = [x for x in c3_ids if x != iid] if i == 0 else []
        row = {
            "incident_id": iid,
            "vendor_id": meta["vendor_id"],
            "days_ago": meta["days_ago"],
            "type": meta["type"],
            "resolution_hours": round(random.uniform(4, 12), 1),
            "repeat_within_90d": True,
            "customer_impact": "moderate",
            "outcome": "Recurring fiber fault at Quincy WA; pattern suggests infrastructure issue",
        }
        if linked:
            row["related_incident_ids"] = linked
        new_rows.append(row)

    for i, (meta, iid) in enumerate(zip(cluster_vendor007, c7_ids)):
        linked = [c7_ids[0], c7_ids[1]] if i == 2 else []
        row = {
            "incident_id": iid,
            "vendor_id": meta["vendor_id"],
            "days_ago": meta["days_ago"],
            "type": meta["type"],
            "resolution_hours": round(random.uniform(5, 14), 1),
            "repeat_within_90d": True,
            "customer_impact": "moderate",
            "outcome": "Cooling cluster recurrence at Atlanta GA — fourth event in 24-day window",
        }
        if linked:
            row["related_incident_ids"] = linked
        new_rows.append(row)

    # --- Layer 4: missing/stale data (10 rows) ---
    layer4_vendors = ["vendor-004", "vendor-004", "vendor-004", "vendor-004",
                      "vendor-002", "vendor-009", "vendor-005", "vendor-004",
                      "vendor-010", "vendor-006"]
    for i, vid in enumerate(layer4_vendors):
        outcome_txt, res_h, impact = OUTCOME_LAYER4[i]
        site = random.choice(VENDOR_SITES[vid])
        row = {
            "incident_id": f"INC-{inc_id}",
            "vendor_id": vid,
            "days_ago": random.randint(1, 90),
            "type": random.choice(INCIDENT_TYPES[vid]),
            "resolution_hours": res_h,
            "repeat_within_90d": random.choice([True, False]),
            "customer_impact": impact,
            "outcome": outcome_txt,
        }
        new_rows.append(row)
        inc_id += 1

    # --- Layer 2: field conflicts, vendor-004 gets 20, others get 5 ---
    # vendor-004 layer-2 rows
    for i in range(20):
        conflict = OUTCOME_LAYER2_VENDOR004[i % len(OUTCOME_LAYER2_VENDOR004)]
        impact_field, outcome_text = conflict
        site = random.choice(VENDOR_SITES["vendor-004"])
        row = {
            "incident_id": f"INC-{inc_id}",
            "vendor_id": "vendor-004",
            "days_ago": random.randint(1, 90),
            "type": random.choice(INCIDENT_TYPES["vendor-004"]),
            "resolution_hours": round(random.uniform(10, 48), 1),
            "repeat_within_90d": random.random() < 0.6,
            "customer_impact": impact_field,
            "outcome": outcome_text,
        }
        new_rows.append(row)
        inc_id += 1

    # other vendors layer-2 conflicts (5 rows spread across v1,v2,v3,v6,v8)
    other_l2_vendors = ["vendor-001", "vendor-002", "vendor-003", "vendor-006", "vendor-008"]
    for vid in other_l2_vendors:
        conflict = random.choice(OUTCOME_LAYER2_CONFLICTS)
        impact_field, outcome_text = conflict
        row = {
            "incident_id": f"INC-{inc_id}",
            "vendor_id": vid,
            "days_ago": random.randint(1, 90),
            "type": random.choice(INCIDENT_TYPES[vid]),
            "resolution_hours": round(random.uniform(3, 24), 1),
            "repeat_within_90d": random.random() < 0.35,
            "customer_impact": impact_field,
            "outcome": outcome_text,
        }
        new_rows.append(row)
        inc_id += 1

    # --- Layer 3: mixed vocabularies (25 rows across all vendors) ---
    l3_vendors = (
        ["vendor-001"] * 2 + ["vendor-002"] * 2 + ["vendor-003"] * 3 +
        ["vendor-004"] * 5 + ["vendor-005"] * 2 + ["vendor-006"] * 2 +
        ["vendor-007"] * 3 + ["vendor-008"] * 2 + ["vendor-009"] * 2 + ["vendor-010"] * 2
    )
    random.shuffle(l3_vendors)
    for j, vid in enumerate(l3_vendors):
        impact = IMPACT_LAYER3_VOCABS[j % len(IMPACT_LAYER3_VOCABS)]
        use_code = random.random() < 0.4
        if use_code:
            outcome_text = random.choice(OUTCOME_CODES)
        else:
            outcome_text = random.choice(OUTCOME_LAYER1)
        row = {
            "incident_id": f"INC-{inc_id}",
            "vendor_id": vid,
            "days_ago": random.randint(1, 90),
            "type": random.choice(INCIDENT_TYPES[vid]),
            "resolution_hours": round(random.uniform(2, 30), 1),
            "repeat_within_90d": random.random() < 0.4,
            "customer_impact": impact,
            "outcome": outcome_text,
        }
        new_rows.append(row)
        inc_id += 1

    # --- Layer 1: inconsistent units (~50 rows, spread across all vendors) ---
    # Fill up to ~100 total using Layer 1 style outcomes
    existing_count = len(outcomes)
    new_count_so_far = len(new_rows)
    remaining = 100 - existing_count - new_count_so_far
    remaining = max(remaining, 0)

    all_vendors_flat = []
    for vid in VENDOR_SITES:
        # vendor-004 gets ~25% of remaining, others share the rest
        weight = 3 if vid == "vendor-004" else 1
        all_vendors_flat.extend([vid] * weight)
    random.shuffle(all_vendors_flat)

    for k in range(remaining):
        vid = all_vendors_flat[k % len(all_vendors_flat)]
        outcome_text = OUTCOME_LAYER1[k % len(OUTCOME_LAYER1)]
        # vendor-001: ~80% clean = minor impact; vendor-004: messy
        if vid == "vendor-001":
            impact = "minor" if random.random() < 0.8 else "moderate"
            res_h = round(random.uniform(4, 10), 1)
            repeat = False
        elif vid == "vendor-004":
            impact = random.choice(["high", "moderate", "minor"])
            res_h = round(random.uniform(20, 50), 1)
            repeat = random.random() < 0.7
        else:
            impact = random.choice(["minor", "moderate", "high"])
            res_h = round(random.uniform(4, 20), 1)
            repeat = random.random() < 0.3
        row = {
            "incident_id": f"INC-{inc_id}",
            "vendor_id": vid,
            "days_ago": random.randint(1, 90),
            "type": random.choice(INCIDENT_TYPES[vid]),
            "resolution_hours": res_h,
            "repeat_within_90d": repeat,
            "customer_impact": impact,
            "outcome": outcome_text,
        }
        new_rows.append(row)
        inc_id += 1

    outcomes.extend(new_rows)
    save_json("data/incident_outcomes.json", outcomes)
    print(f"incident_outcomes.json: {len(outcomes)} total rows ({len(new_rows)} added)")
    return outcomes


# ---------------------------------------------------------------------------
# 3. communications.json
# ---------------------------------------------------------------------------

def gen_communications():
    comms = load_json("data/communications.json")

    new_rows = []

    additions = [
        # vendor-004 negative threads
        {"vendor_id": "vendor-004", "days_ago": 2,  "channel": "Email",  "topic": "Boydton VA power failure escalation", "sentiment": "negative", "summary": "VP-level escalation thread following fourth power event in 60 days. Contract review requested."},
        {"vendor_id": "vendor-004", "days_ago": 7,  "channel": "Teams",  "topic": "SLA breach formal notice",            "sentiment": "negative", "summary": "Formal notice of SLA breach sent to vendor account manager. Response pending."},
        {"vendor_id": "vendor-004", "days_ago": 14, "channel": "Email",  "topic": "PIP follow-up",                       "sentiment": "negative", "summary": "Follow-up on PIP milestones. Vendor acknowledged two of five corrective items; three remain open."},
        {"vendor_id": "vendor-004", "days_ago": 21, "channel": "Call",   "topic": "Executive review meeting notes",       "sentiment": "negative", "summary": "Executive QBR. Vendor cited supply-chain delays as root cause. Operations team disputed explanation."},
        {"vendor_id": "vendor-004", "days_ago": 30, "channel": "Email",  "topic": "Cooling event post-mortem",           "sentiment": "negative", "summary": "[automated summary failed]"},
        # vendor-002 stale comms
        {"vendor_id": "vendor-002", "days_ago": 40, "channel": "Email",  "topic": "Quarterly status — no response",      "sentiment": "neutral",  "summary": "Quarterly status request sent. No response received as of 40 days ago."},
        {"vendor_id": "vendor-002", "days_ago": 55, "channel": "Teams",  "topic": "Link flap follow-up",                 "sentiment": "negative", "summary": "Follow-up on recurring link flap incidents. Vendor acknowledged but provided no timeline."},
        {"vendor_id": "vendor-002", "days_ago": 62, "channel": "Email",  "topic": "SLA metrics review — overdue",        "sentiment": "neutral",  "summary": "Requested SLA metrics package. No response. Communication gap flagged."},
        # vendor-005 thin comms
        {"vendor_id": "vendor-005", "days_ago": 5,  "channel": "Teams",  "topic": "Cheyenne WY backhaul check",          "sentiment": "neutral",  "summary": "Routine check-in. No issues flagged by vendor."},
        {"vendor_id": "vendor-005", "days_ago": 18, "channel": "Email",  "topic": "Tower equipment inspection",          "sentiment": "positive", "summary": "Vendor provided inspection report. All tower equipment within spec."},
        {"vendor_id": "vendor-005", "days_ago": 35, "channel": "Teams",  "topic": "Microwave link degradation review",   "sentiment": "neutral",  "summary": "Discussion of recent link degradation event. Vendor attributed to weather; monitoring increased."},
        # vendor-009 thin comms
        {"vendor_id": "vendor-009", "days_ago": 8,  "channel": "Email",  "topic": "Phoenix AZ sensor alert review",     "sentiment": "neutral",  "summary": "Review of recent sensor alert pattern. Vendor indicated firmware update resolves issue."},
        {"vendor_id": "vendor-009", "days_ago": 22, "channel": "Teams",  "topic": "Network monitoring gap",              "sentiment": "negative", "summary": "Discussion of monitoring blackout period. Data gaps remain unexplained."},
        {"vendor_id": "vendor-009", "days_ago": 48, "channel": "Call",   "topic": "Incident reporting completeness",     "sentiment": "neutral",  "summary": "Vendor acknowledged incomplete incident data. Committed to backfill within 30 days."},
        # vendor-007 additional
        {"vendor_id": "vendor-007", "days_ago": 4,  "channel": "Teams",  "topic": "Atlanta GA cooling cluster alert",   "sentiment": "negative", "summary": "Alert raised on third cooling event in three weeks. Vendor dispatched senior engineer."},
        {"vendor_id": "vendor-007", "days_ago": 11, "channel": "Email",  "topic": "Cooling system RCA",                 "sentiment": "neutral",  "summary": "Root cause analysis submitted. Vendor identified faulty CRAC unit batch as common cause."},
        # vendor-010 additional
        {"vendor_id": "vendor-010", "days_ago": 6,  "channel": "Email",  "topic": "Chiller fault tracking",             "sentiment": "neutral",  "summary": "Monthly chiller health report. Two units flagged for preventive maintenance."},
        {"vendor_id": "vendor-010", "days_ago": 28, "channel": "Teams",  "topic": "Repeat HVAC alarm pattern",          "sentiment": "negative", "summary": "Operations flagged recurring HVAC alarm pattern. Vendor scheduled site visit."},
        # vendor-001 positive
        {"vendor_id": "vendor-001", "days_ago": 6,  "channel": "Email",  "topic": "Proactive fiber inspection report",  "sentiment": "positive", "summary": "Vendor submitted proactive inspection results. No anomalies detected at Quincy WA."},
        {"vendor_id": "vendor-001", "days_ago": 20, "channel": "Teams",  "topic": "Capacity planning update",           "sentiment": "positive", "summary": "FiberWorks shared updated capacity plan. All milestones on track for Q3."},
    ]

    new_rows.extend(additions)
    comms.extend(new_rows)
    save_json("data/communications.json", comms)
    print(f"communications.json: {len(comms)} total rows ({len(new_rows)} added)")
    return comms


# ---------------------------------------------------------------------------
# 4. sla_records.json
# ---------------------------------------------------------------------------

def gen_sla_records():
    records = load_json("data/sla_records.json")

    existing_vendor_ids = {r["vendor_id"] for r in records}

    new_entries = []

    if "vendor-005" not in existing_vendor_ids:
        new_entries.append({
            "vendor_id": "vendor-005",
            "ack_minutes_target": 45,
            "completion_hours_target": 12,
            "breach_count_90d": 3,
            "breach_rate_90d": 0.17,
            "avg_ack_minutes_90d": 37.2,
            "avg_completion_hours_90d": 11.8,
            "tier_expectation": "Tier 2 SLA — relaxed",
        })

    if "vendor-010" not in existing_vendor_ids:
        # vendor-010 already exists
        pass

    # Update vendor-009 to reflect expanded dataset
    for r in records:
        if r["vendor_id"] == "vendor-009":
            r["breach_count_90d"] = 4
            r["breach_rate_90d"] = 0.22
            r["avg_ack_minutes_90d"] = 41.3
            r["avg_completion_hours_90d"] = 13.1
        if r["vendor_id"] == "vendor-004":
            r["breach_count_90d"] = 22
            r["breach_rate_90d"] = 0.88
            r["avg_ack_minutes_90d"] = 94.5
            r["avg_completion_hours_90d"] = 38.2

    records.extend(new_entries)
    save_json("data/sla_records.json", records)
    print(f"sla_records.json: {len(records)} total rows ({len(new_entries)} added)")
    return records


# ---------------------------------------------------------------------------
# 5. vendor_queries.jsonl  (Q81–Q110)
# ---------------------------------------------------------------------------

NEW_QUERIES = [
    {
        "id": "Q81",
        "query": "Did DataCore Logistics actually have moderate customer impact this quarter, or were those incidents worse than they look?",
        "vendor_id": "vendor-004",
        "evidence_quality": "conflicted",
        "ground_truth": "The structured customer_impact field frequently says 'moderate' while outcome text describes VP-level escalations, 6-hour outages, and executive reviews. The agent should surface this conflict and not silently accept the structured field.",
        "context": "Multiple vendor-004 incidents have customer_impact='moderate' but outcome text references executive escalations, SLA breaches, and multi-hour outages. 20+ such conflicted rows exist across the dataset.",
        "expected_behavior": "The agent should surface the conflict between the structured field (customer_impact: moderate) and the outcome text (90-minute outage, executive escalation). It should not silently pick one signal. A good response notes the inconsistency and either recommends reconciliation or weights the more severe signal with justification.",
        "reference_facts": "vendor-004 has 20+ incidents where customer_impact='moderate' or 'low' but outcome text describes executive escalations, full pod shutdowns, and SLA breaches lasting 4–8 hours.",
        "expected_failure_mode": "disambiguation_field_conflict",
    },
    {
        "id": "Q82",
        "query": "What's the total downtime DataCore caused at Boydton VA in the last 90 days?",
        "vendor_id": "vendor-004",
        "evidence_quality": "partial",
        "ground_truth": "Outcome text uses mixed units: minutes, fractional hours, narrative phrases like 'half a day', and exact H:MM formats. The agent must normalize all to hours before summing. Skipping non-standard rows undercounts; double-counting converted rows overcounts.",
        "context": "vendor-004 incident outcomes at Boydton VA include rows like '90 minutes of downtime', '4-hour outage', 'Half a day of degraded performance', 'Downtime: 0.75 hours', 'Total outage duration: 3 hours 20 minutes'.",
        "expected_behavior": "The agent should normalize units. Free-text outcome durations should be converted to a common unit (hours) before computing totals. Responses that double-count or skip rows with non-standard units score low.",
        "reference_facts": "Outcome durations at Boydton VA for vendor-004 use at least 5 distinct formats. Correct approach normalizes all to decimal hours. Cluster of 3 incidents (5, 12, 19 days ago) adds approximately 10–25 hours depending on extraction.",
        "expected_failure_mode": "disambiguation_unit_mismatch",
    },
    {
        "id": "Q83",
        "query": "Compare incident severity across our vendors over the last quarter.",
        "vendor_id": None,
        "evidence_quality": "partial",
        "ground_truth": "The dataset uses at least 5 distinct vocabulary systems for severity: minor/moderate/high, Severity 1-4, P1/P2/P3, Critical/Major/Minor, Tier 1-2 impact, and numeric 1-4. A correct comparison requires mapping these to a unified scale before comparing vendors.",
        "context": "incident_outcomes.json contains ~25 rows using non-standard customer_impact vocabularies (Severity 1-4, P1-P3, Critical/Major/Minor, Tier 1-2, numeric). Standard rows use minor/moderate/high.",
        "expected_behavior": "The agent should recognize Severity 1 / P1 / Critical / Tier 1 / 1 as equivalent for the purpose of cross-vendor comparison. Responses that treat them as separate categories score low.",
        "reference_facts": "Severity 1 ≈ P1 ≈ Critical ≈ Tier 1 impact ≈ 1 (highest). Severity 4 ≈ P3 ≈ Minor ≈ 4 (lowest). ~25 rows use non-standard vocabulary spread across multiple vendors.",
        "expected_failure_mode": "disambiguation_vocabulary",
    },
    {
        "id": "Q84",
        "query": "Are there repeat issues we're missing in the data?",
        "vendor_id": None,
        "evidence_quality": "partial",
        "ground_truth": "Two clusters exist with related_incident_ids explicitly set (vendor-004 Boydton VA, vendor-003 Quincy WA). A third cluster (vendor-007 Atlanta GA) has linked rows on only some entries. The agent should detect all clusters including those with no explicit links, by correlating vendor+site+days_ago.",
        "context": "Cluster 1: vendor-004 Boydton VA, incidents at 5, 12, 19 days ago. Cluster 2: vendor-003 Quincy WA, incidents at 2, 9, 16 days ago. Cluster 3: vendor-007 Atlanta GA, incidents at 3, 10, 17, 24 days ago. Not all have related_incident_ids populated.",
        "expected_behavior": "Should detect clusters of repeat incidents even for unlinked rows, by correlating site+vendor+days_ago patterns. Should not rely solely on the related_incident_ids field.",
        "reference_facts": "3 clusters across vendor-004/Boydton VA, vendor-003/Quincy WA, vendor-007/Atlanta GA. Cluster detection via date proximity is required. Some rows in each cluster lack related_incident_ids.",
        "expected_failure_mode": "under_pattern_attribution",
    },
    {
        "id": "Q85",
        "query": "How reliable is our incident reporting for NorthStar Networks?",
        "vendor_id": "vendor-002",
        "evidence_quality": "sparse",
        "ground_truth": "vendor-002 has stale communications (last contact 40+ days ago, no response to quarterly request), limited incident data, and at least one conflict row where customer_impact and outcome disagree. The agent should flag these as reliability concerns.",
        "context": "vendor-002: 20 dispatches, ~50% SLA-met. Communications: last thread 40 days ago with no vendor response. At least 1 incident has customer_impact/outcome conflict. SLA records show partial breach history.",
        "expected_behavior": "Should surface data quality gaps: stale communications, missing or inconsistent fields, and note where the reporting cannot be trusted for decision-making.",
        "reference_facts": "vendor-002 last comms response is 40+ days old. Quarterly status request unanswered. One conflict incident row. Resolution data for at least one incident flagged as TBD.",
        "expected_failure_mode": "disambiguation_field_conflict",
    },
    {
        "id": "Q86",
        "query": "DataCore says these were moderate-impact incidents. Do the outcomes support that?",
        "vendor_id": "vendor-004",
        "evidence_quality": "conflicted",
        "ground_truth": "No — the outcome text repeatedly contradicts the 'moderate' label. At least 10 vendor-004 incidents describe executive escalations, full pod shutdowns, VP briefings, and multi-hour SLA breaches while customer_impact is set to 'moderate' or 'low'.",
        "context": "vendor-004 has 20+ rows where customer_impact='moderate' but outcome text mentions VP-level escalation, complete service disruption, 6-hour outages, and post-incident reviews.",
        "expected_behavior": "The agent should surface the conflict between the structured field (customer_impact) and the outcome text. It should not silently pick one signal. A good response notes the inconsistency and either recommends reconciliation or weights the more severe signal with justification.",
        "reference_facts": "20+ vendor-004 incidents with customer_impact='moderate' or 'low' contradicted by outcome text referencing VP escalations, full shutdowns, and SLA formal breaches.",
        "expected_failure_mode": "disambiguation_field_conflict",
    },
    {
        "id": "Q87",
        "query": "Can you total up all downtime hours for PacificCom this quarter?",
        "vendor_id": "vendor-003",
        "evidence_quality": "partial",
        "ground_truth": "Outcome text for vendor-003 uses mixed formats: '45 min', '2.5h', 'Brief disruption (~15 min)', 'Total outage duration: 3 hours 20 minutes'. Normalization to hours required. Three cluster incidents at Quincy WA (2, 9, 16 days ago) contribute to the total.",
        "context": "vendor-003 incident outcomes use mixed time formats. At least 3 incidents form a cluster at Quincy WA with similar types — suggesting a pattern rather than independent events.",
        "expected_behavior": "The agent should normalize units. Free-text outcome durations should be converted to a common unit (hours) before computing totals. Responses that double-count or skip rows with non-standard units score low.",
        "reference_facts": "vendor-003 Quincy WA cluster: 3 incidents at days 2, 9, 16. Outcome text uses at least 3 different time formats across vendor-003 rows.",
        "expected_failure_mode": "disambiguation_unit_mismatch",
    },
    {
        "id": "Q88",
        "query": "Which vendors use severity-number rankings instead of text labels in their incident reports?",
        "vendor_id": None,
        "evidence_quality": "partial",
        "ground_truth": "Several rows in incident_outcomes.json use numeric customer_impact values ('1', '2', '3', '4') or mixed-vocabulary labels (P1/P2/P3, Severity 1-4). These are spread across multiple vendors. The agent should identify rows where customer_impact is numeric or non-standard.",
        "context": "~25 incident rows use non-standard customer_impact vocabulary including numeric strings '1'-'4', Severity 1-4, P1-P3, Critical/Major/Minor, and Tier 1-2.",
        "expected_behavior": "The agent should recognize Severity 1 / P1 / Critical / Tier 1 / 1 as equivalent for the purpose of cross-vendor comparison. Responses that treat them as separate categories score low.",
        "reference_facts": "Non-standard vocabulary rows include at least: numeric '1'-'4', 'Severity 1-4', 'P1'-'P3', 'Tier 1 impact', 'Tier 2 impact'. Distributed across vendor-001 through vendor-010.",
        "expected_failure_mode": "disambiguation_vocabulary",
    },
    {
        "id": "Q89",
        "query": "Are there any incidents where the recorded severity seems too low for what actually happened?",
        "vendor_id": None,
        "evidence_quality": "conflicted",
        "ground_truth": "Yes — multiple rows across vendor-004, vendor-003, vendor-006, vendor-008, and others have customer_impact set to 'minor', 'low', or 'moderate' while outcome text describes major escalations, repeated failures, or multi-hour outages.",
        "context": "Layer 2 conflicts exist in incident_outcomes.json: customer_impact='minor' with outcome 'Repeat issue for the third time this month', customer_impact='low' with 'SLA breach triggered executive briefing', and similar contradictions.",
        "expected_behavior": "The agent should surface the conflict between the structured field (customer_impact) and the outcome text. It should not silently pick one signal. A good response notes the inconsistency and either recommends reconciliation or weights the more severe signal with justification.",
        "reference_facts": "25+ rows with field/text conflicts. Examples: customer_impact='minor', outcome='Complete power loss to pod B; recovery required full generator failover — 4+ hours'. Or customer_impact='low', outcome='Three-site simultaneous outage; full incident command activated'.",
        "expected_failure_mode": "disambiguation_field_conflict",
    },
    {
        "id": "Q90",
        "query": "For DataCore at Boydton VA, are the three recent incidents related or independent?",
        "vendor_id": "vendor-004",
        "evidence_quality": "partial",
        "ground_truth": "The three incidents (5, 12, 19 days ago) form a cluster. Two have related_incident_ids populated; one does not. The agent should identify the cluster using date/site/vendor correlation, not just the related_incident_ids field.",
        "context": "vendor-004 Boydton VA cluster: INC-1500 (5 days ago), INC-1501 (12 days ago), INC-1502 (19 days ago). Two have related_incident_ids; the third does not.",
        "expected_behavior": "Should detect clusters of repeat incidents even for unlinked rows, by correlating site+vendor+days_ago patterns. Should not rely solely on the related_incident_ids field.",
        "reference_facts": "Three incidents at vendor-004/Boydton VA within 19 days. Types: Power failure, Generator fault, UPS failure. repeat_within_90d=true on all three. Only two have explicit related_incident_ids.",
        "expected_failure_mode": "under_pattern_attribution",
    },
    {
        "id": "Q91",
        "query": "How much total downtime did vendor-004 cause last month across all sites?",
        "vendor_id": "vendor-004",
        "evidence_quality": "partial",
        "ground_truth": "Outcome text contains at least 8 distinct duration formats for vendor-004. Normalization to decimal hours is required. Some rows have resolution_hours=-1 (unknown). The agent should handle both sources and flag where data is missing.",
        "context": "vendor-004 incidents use outcome text with formats: '90 minutes', '4-hour outage', 'Half a day', 'Downtime: 0.75 hours', '3 hours 20 minutes', '6 hours'. Plus some rows have resolution_hours=-1.",
        "expected_behavior": "The agent should normalize units. Free-text outcome durations should be converted to a common unit (hours) before computing totals. Responses that double-count or skip rows with non-standard units score low.",
        "reference_facts": "vendor-004 has rows with resolution_hours=-1 (sentinel for unknown) and outcome texts with at least 5 different time unit formats. Correct total requires normalization and should note excluded/unknown rows.",
        "expected_failure_mode": "disambiguation_unit_mismatch",
    },
    {
        "id": "Q92",
        "query": "Which incidents have missing or unreliable data fields?",
        "vendor_id": None,
        "evidence_quality": "mixed",
        "ground_truth": "Several categories: (1) resolution_hours=-1 rows, (2) customer_impact='TBD' or 'pending review', (3) outcome='[automated summary failed]', (4) dispatch rows with ack_minutes=null. The agent should enumerate all categories.",
        "context": "Layer 4 data quality issues: ~10 incidents with resolution_hours=-1, ~10 with customer_impact='TBD'/'pending review', ~5 with outcome='[automated summary failed]'. Plus ~5% of dispatch rows with ack_minutes=null.",
        "expected_behavior": "Should enumerate all categories of missing/unreliable data: sentinel values, placeholder text, null fields, and automated summary failures. A good response counts and categorizes these without speculating on content.",
        "reference_facts": "Known unreliable field patterns: resolution_hours=-1 (~10 rows), customer_impact in ['TBD','pending review'] (~10 rows), outcome='[automated summary failed]' (~5 rows), ack_minutes=null in dispatches (~5% of rows).",
        "expected_failure_mode": "none_calibrated",
    },
    {
        "id": "Q93",
        "query": "Is there a cluster of failures at any single site in the last two weeks?",
        "vendor_id": None,
        "evidence_quality": "partial",
        "ground_truth": "Yes — three clusters exist within 14-day windows: vendor-004/Boydton VA (days 5, 12), vendor-003/Quincy WA (days 2, 9), vendor-007/Atlanta GA (days 3, 10). All three qualify as within-14-day clusters.",
        "context": "Cluster data: vendor-004 Boydton VA at days 5 and 12; vendor-003 Quincy WA at days 2 and 9; vendor-007 Atlanta GA at days 3 and 10.",
        "expected_behavior": "Should detect clusters of repeat incidents even for unlinked rows, by correlating site+vendor+days_ago patterns. Should not rely solely on the related_incident_ids field.",
        "reference_facts": "Three site clusters with incidents within 14 days of each other. None are completely linked via related_incident_ids — pattern detection required.",
        "expected_failure_mode": "under_pattern_attribution",
    },
    {
        "id": "Q94",
        "query": "Compare DataCore and FiberWorks on customer impact — which vendor caused more business disruption?",
        "vendor_id": None,
        "evidence_quality": "conflicted",
        "ground_truth": "A naive comparison using the customer_impact field alone would undercount DataCore disruption — its 'moderate' labels mask VP escalations and hour-long outages. FiberWorks data is clean and self-consistent. The agent should weight outcome text evidence for DataCore.",
        "context": "vendor-004 has 20+ field/text conflicts showing underreported severity. vendor-001 has clean, consistent reporting with minor/moderate labels that match outcome text.",
        "expected_behavior": "The agent should surface the conflict between the structured field (customer_impact) and the outcome text. It should not silently pick one signal. A good response notes the inconsistency and either recommends reconciliation or weights the more severe signal with justification.",
        "reference_facts": "vendor-001: ~80% clean rows, customer_impact consistent with outcome text. vendor-004: 20+ rows where customer_impact='moderate'/'low' contradicted by outcome text referencing executive escalations and hour-long outages.",
        "expected_failure_mode": "disambiguation_field_conflict",
    },
    {
        "id": "Q95",
        "query": "When DataCore records say 'high impact,' is that consistent with how they describe outcomes in the notes?",
        "vendor_id": "vendor-004",
        "evidence_quality": "conflicted",
        "ground_truth": "Inconsistency runs in both directions. Some 'high' rows have outcome text that is trivial ('resolved in 12 min, no escalation'). Some 'moderate' rows have outcome text describing VP escalations and 6-hour outages. Neither direction is consistent.",
        "context": "vendor-004 Layer 2 conflicts include: customer_impact='high' with trivial outcome text, and customer_impact='moderate' with severe outcome text. Both patterns present.",
        "expected_behavior": "The agent should surface the conflict between the structured field (customer_impact) and the outcome text. It should not silently pick one signal. A good response notes the inconsistency and either recommends reconciliation or weights the more severe signal with justification.",
        "reference_facts": "vendor-004 bidirectional conflicts: 'high'→trivial outcome (3+ rows), 'moderate'/'low'→severe outcome (15+ rows). No consistent mapping between field and text.",
        "expected_failure_mode": "disambiguation_field_conflict",
    },
    {
        "id": "Q96",
        "query": "Some vendors label their incidents with P1/P2/P3. Can you map those to our standard severity scale?",
        "vendor_id": None,
        "evidence_quality": "partial",
        "ground_truth": "P1 maps to 'high' (or Critical/Severity 1/Tier 1). P2 maps to 'moderate' (Severity 2/Major/Tier 2). P3 maps to 'minor' (Severity 3-4/Minor). The agent should make this mapping explicit and apply it consistently.",
        "context": "~25 incidents use P1/P2/P3 vocabulary. The standard vocabulary is minor/moderate/high. Severity 1/Critical/Tier 1 are equivalent to high/P1.",
        "expected_behavior": "The agent should recognize Severity 1 / P1 / Critical / Tier 1 / 1 as equivalent for the purpose of cross-vendor comparison. Responses that treat them as separate categories score low.",
        "reference_facts": "Mapping: P1=Severity 1=Critical=Tier 1 impact=1 → high. P2=Severity 2=Major=Tier 2 impact=2 → moderate. P3=Severity 3=Minor=3 → minor/low.",
        "expected_failure_mode": "disambiguation_vocabulary",
    },
    {
        "id": "Q97",
        "query": "How many Severity 1 or P1 or Critical incidents did we have this quarter?",
        "vendor_id": None,
        "evidence_quality": "partial",
        "ground_truth": "All three terms refer to the same severity tier. The agent must count rows where customer_impact is in ['Severity 1', 'P1', 'Critical', 'Tier 1 impact', '1', 'high'] as equivalent. Treating them as separate buckets will undercount.",
        "context": "Incidents with high-equivalent customer_impact use at least 6 different vocabulary terms: 'high', 'Severity 1', 'P1', 'Critical', 'Tier 1 impact', '1'.",
        "expected_behavior": "The agent should recognize Severity 1 / P1 / Critical / Tier 1 / 1 as equivalent for the purpose of cross-vendor comparison. Responses that treat them as separate categories score low.",
        "reference_facts": "Distinct high-tier labels present: 'high', 'Severity 1', 'P1', 'Critical', 'Tier 1 impact', '1'. Approximate total high-tier incidents across all vendors: 20-35 depending on normalization.",
        "expected_failure_mode": "disambiguation_vocabulary",
    },
    {
        "id": "Q98",
        "query": "Are any vendor-009 incident outcomes flagged as stale or incomplete?",
        "vendor_id": "vendor-009",
        "evidence_quality": "sparse",
        "ground_truth": "vendor-009 has at least one incident with resolution_hours=-1 and customer_impact='TBD'. The agent should identify these and note that incomplete data limits reliability of vendor-009 performance assessment.",
        "context": "vendor-009 has limited data overall (thin comms, sparse incidents). At least 1 incident has stale/incomplete fields. Communications log shows monitoring gaps and unfilled backfill commitment.",
        "expected_behavior": "Should identify specific incomplete rows and note that data gaps prevent confident performance assessment. Should not fabricate conclusions from absent data.",
        "reference_facts": "vendor-009: 1+ incidents with resolution_hours=-1 or customer_impact='TBD'. Comms thread at 22 days ago notes unresolved monitoring blackout. Vendor committed to backfill but gap persists.",
        "expected_failure_mode": "none_calibrated",
    },
    {
        "id": "Q99",
        "query": "Is there evidence of recurring problems at the same sites within short windows?",
        "vendor_id": None,
        "evidence_quality": "partial",
        "ground_truth": "Three documented clusters: vendor-004/Boydton VA (power/cooling events, 5-19 days ago), vendor-003/Quincy WA (fiber faults, 2-16 days ago), vendor-007/Atlanta GA (cooling events, 3-24 days ago). All qualify as recurring site-level patterns.",
        "context": "Clusters identifiable by vendor+site+incident_type+days_ago proximity. Some have related_incident_ids; others require pattern matching.",
        "expected_behavior": "Should detect clusters of repeat incidents even for unlinked rows, by correlating site+vendor+days_ago patterns. Should not rely solely on the related_incident_ids field.",
        "reference_facts": "3 clusters documented in data. Cluster threshold: same vendor+site, within 14-21 days, similar incident types. At least one cluster (vendor-007) has no complete related_incident_ids chain.",
        "expected_failure_mode": "under_pattern_attribution",
    },
    {
        "id": "Q100",
        "query": "What is the total duration of outages for MountainRidge in the past 60 days?",
        "vendor_id": "vendor-005",
        "evidence_quality": "sparse",
        "ground_truth": "vendor-005 outcome text uses mixed formats. Correct approach: extract durations from text, normalize to hours, sum. Flag rows with resolution_hours=-1 as unknowns. Evidence is sparse (20 total incidents) so totals carry uncertainty.",
        "context": "vendor-005 has ~20 incidents. Outcome text includes varied formats. At least 1 row has resolution_hours=-1.",
        "expected_behavior": "The agent should normalize units. Free-text outcome durations should be converted to a common unit (hours) before computing totals. Responses that double-count or skip rows with non-standard units score low.",
        "reference_facts": "vendor-005 Cheyenne WY. ~20 incidents, some with mixed-format duration text. 1+ rows with unknown resolution time. Agent should note uncertainty from sparse data.",
        "expected_failure_mode": "disambiguation_unit_mismatch",
    },
    {
        "id": "Q101",
        "query": "DataCore's last five incidents all say 'moderate' customer impact. Is that classification accurate?",
        "vendor_id": "vendor-004",
        "evidence_quality": "conflicted",
        "ground_truth": "The classification is systematically inaccurate. Outcome text for those rows describes VP escalations, 6-hour outages, SLA formal breaches, and post-incident reviews — all indicators of high or critical impact. The 'moderate' label appears to be underreported.",
        "context": "Recent vendor-004 incidents consistently show customer_impact='moderate' while outcomes describe severe events. This pattern has been flagged in communications (VP escalation thread, PIP, contract review).",
        "expected_behavior": "The agent should surface the conflict between the structured field (customer_impact) and the outcome text. It should not silently pick one signal. A good response notes the inconsistency and either recommends reconciliation or weights the more severe signal with justification.",
        "reference_facts": "Last 5 vendor-004 incidents: customer_impact='moderate' on all, but outcomes reference VP-level escalation (2 rows), SLA breach (3 rows), full pod shutdown (1 row). Comms log corroborates severity.",
        "expected_failure_mode": "disambiguation_field_conflict",
    },
    {
        "id": "Q102",
        "query": "Do our vendors use consistent terminology for incident severity?",
        "vendor_id": None,
        "evidence_quality": "mixed",
        "ground_truth": "No. At least 6 different vocabulary systems are in use: minor/moderate/high (standard), Severity 1-4, P1-P3, Critical/Major/Minor, Tier 1-2 impact, and numeric 1-4. Additionally, empty string and TBD/pending review appear as values.",
        "context": "~25 rows use non-standard customer_impact vocabularies in addition to the standard minor/moderate/high. Some rows have empty string or TBD.",
        "expected_behavior": "The agent should recognize Severity 1 / P1 / Critical / Tier 1 / 1 as equivalent for the purpose of cross-vendor comparison. Responses that treat them as separate categories score low.",
        "reference_facts": "Vocabulary inventory: 'minor','moderate','high','Severity 1-4','P1-P3','Critical','Major','Minor','Tier 1 impact','Tier 2 impact','1','2','3','4','','TBD','pending review'. 17 distinct values in use.",
        "expected_failure_mode": "disambiguation_vocabulary",
    },
    {
        "id": "Q103",
        "query": "Which incidents have outcome text that contradicts the customer_impact field?",
        "vendor_id": None,
        "evidence_quality": "mixed",
        "ground_truth": "At least 25 incidents have a clear contradiction. Primary pattern: customer_impact='moderate' or 'low' with outcome text describing executive escalations, VP briefings, SLA breaches, or multi-hour outages. Secondary pattern: customer_impact='high' with trivial outcome text.",
        "context": "Layer 2 conflict rows: 20+ in vendor-004, 5 spread across vendor-001, vendor-002, vendor-003, vendor-006, vendor-008.",
        "expected_behavior": "The agent should surface the conflict between the structured field (customer_impact) and the outcome text. It should not silently pick one signal. A good response notes the inconsistency and either recommends reconciliation or weights the more severe signal with justification.",
        "reference_facts": "25 explicitly conflicted rows. vendor-004 has the most (20+). Both directions present: underreported severity (moderate→severe outcome) and overreported severity (high→trivial outcome).",
        "expected_failure_mode": "disambiguation_field_conflict",
    },
    {
        "id": "Q104",
        "query": "Are there any hidden repeat-issue patterns at vendor-003's Quincy WA site?",
        "vendor_id": "vendor-003",
        "evidence_quality": "partial",
        "ground_truth": "Yes — three fiber-related incidents at Quincy WA within 14 days (days 2, 9, 16). Only the first has related_incident_ids populated. The pattern is detectable via temporal and type correlation, not just explicit links.",
        "context": "vendor-003 Quincy WA: INC cluster at days_ago 2, 9, 16. Types: Fiber cut, Splice failure, Cable damage. repeat_within_90d=True on all three. Only day-2 incident has related_incident_ids.",
        "expected_behavior": "Should detect clusters of repeat incidents even for unlinked rows, by correlating site+vendor+days_ago patterns. Should not rely solely on the related_incident_ids field.",
        "reference_facts": "3 incidents at vendor-003/Quincy WA within 16 days. Pattern: fiber-type incidents recurring at ~7-day intervals. Only 1 of 3 has explicit cross-reference links.",
        "expected_failure_mode": "under_pattern_attribution",
    },
    {
        "id": "Q105",
        "query": "For Sentinel Network Services, how many of their incidents actually have complete data?",
        "vendor_id": "vendor-009",
        "evidence_quality": "sparse",
        "ground_truth": "vendor-009 has ~20 incidents total. At least 1-2 have resolution_hours=-1 or customer_impact='TBD'. Communications show an acknowledged monitoring blackout and unfulfilled backfill commitment. Complete data count should be stated with explicit caveats.",
        "context": "vendor-009 data: sparse overall, monitoring blackout acknowledged in comms, at least 1 Layer 4 incident (TBD/pending). Total incident count: ~20 after expansion.",
        "expected_behavior": "Should identify specific incomplete rows and note that data gaps prevent confident performance assessment. Should not fabricate conclusions from absent data.",
        "reference_facts": "vendor-009: ~20 total incidents. Incomplete data indicators: resolution_hours=-1 (1+), customer_impact='TBD' (1+), monitoring blackout period noted in communications.",
        "expected_failure_mode": "none_calibrated",
    },
    {
        "id": "Q106",
        "query": "If I sum up downtime across all incidents for the last 90 days, what do I get?",
        "vendor_id": None,
        "evidence_quality": "partial",
        "ground_truth": "Cannot produce a single reliable total without normalization. Issues: (1) outcome text uses mixed units, (2) resolution_hours=-1 rows are unknowns, (3) some rows have outcome='[automated summary failed]'. Agent must normalize, flag unknowns, and produce a range with caveats.",
        "context": "Across all ~100 incidents: mixed duration text formats, ~10 rows with resolution_hours=-1, ~5 rows with automated summary failures. Normalization is prerequisite to any total.",
        "expected_behavior": "The agent should normalize units. Free-text outcome durations should be converted to a common unit (hours) before computing totals. Responses that double-count or skip rows with non-standard units score low.",
        "reference_facts": "Total across all ~100 incidents requires: (1) normalizing outcome text durations to hours, (2) excluding resolution_hours=-1 rows and flagging them, (3) noting automated summary failures as irrecoverable gaps.",
        "expected_failure_mode": "disambiguation_unit_mismatch",
    },
    {
        "id": "Q107",
        "query": "Can you tell me which vendor-004 incidents escalated to VP level based on the outcome notes?",
        "vendor_id": "vendor-004",
        "evidence_quality": "partial",
        "ground_truth": "At least 5 vendor-004 outcome texts explicitly mention 'VP-level escalation' or 'executive escalation'. The agent should identify these by parsing free text, not relying on the customer_impact field (which underreports severity).",
        "context": "vendor-004 outcome text examples: 'VP-level escalation triggered', 'executive briefing', 'VP placed on watch list', 'executive QBR'. customer_impact field does NOT reliably flag these rows.",
        "expected_behavior": "The agent should surface the conflict between the structured field (customer_impact) and the outcome text. It should not silently pick one signal. A good response notes the inconsistency and either recommends reconciliation or weights the more severe signal with justification.",
        "reference_facts": "VP/executive escalation keywords in vendor-004 outcome text: 'VP-level escalation triggered' (2 rows), 'executive briefing' (1 row), 'executive review' (1 row), 'VP placed on watch list' (1 row). customer_impact on these rows: mostly 'moderate' or 'low'.",
        "expected_failure_mode": "disambiguation_field_conflict",
    },
    {
        "id": "Q108",
        "query": "How many vendor incidents were labeled Critical or Severity 1 or P1 in the last quarter?",
        "vendor_id": None,
        "evidence_quality": "partial",
        "ground_truth": "These are all equivalent high-tier labels. The count requires unioning rows where customer_impact is in ['Critical','Severity 1','P1','Tier 1 impact','1','high']. Treating them as separate reduces the count incorrectly.",
        "context": "~25 rows use non-standard vocabulary. High-tier equivalents: 'Severity 1', 'P1', 'Critical', 'Tier 1 impact', '1'. Standard high-tier: 'high'.",
        "expected_behavior": "The agent should recognize Severity 1 / P1 / Critical / Tier 1 / 1 as equivalent for the purpose of cross-vendor comparison. Responses that treat them as separate categories score low.",
        "reference_facts": "High-tier label distribution: 'high' (most rows), 'Severity 1' (some), 'P1' (some), 'Critical' (some), 'Tier 1 impact' (some), '1' (some). Correct count unions all six.",
        "expected_failure_mode": "disambiguation_vocabulary",
    },
    {
        "id": "Q109",
        "query": "For vendors with 'TBD' or 'pending review' impact fields, what can we actually conclude?",
        "vendor_id": None,
        "evidence_quality": "sparse",
        "ground_truth": "Rows with customer_impact='TBD' or 'pending review' have no usable severity signal from that field. The agent can fall back to outcome text and resolution_hours if available, but should clearly note the limitation and avoid conclusions that depend on the missing field.",
        "context": "~10 incidents across vendor-002, vendor-004, vendor-005, vendor-006, vendor-009, vendor-010 have customer_impact='TBD' or 'pending review'.",
        "expected_behavior": "Should identify specific incomplete rows and note that data gaps prevent confident performance assessment. Should not fabricate conclusions from absent data.",
        "reference_facts": "~10 rows with customer_impact in ['TBD','pending review']. Spread across 6 vendors. Some also have resolution_hours=-1 compounding the data gap.",
        "expected_failure_mode": "none_calibrated",
    },
    {
        "id": "Q110",
        "query": "Which vendor has the biggest gap between their official severity rating and what the outcome text describes?",
        "vendor_id": None,
        "evidence_quality": "conflicted",
        "ground_truth": "vendor-004 has the largest gap. 20+ rows show customer_impact='moderate' or 'low' while outcome text describes VP escalations, SLA breaches, pod shutdowns, and 6-hour outages. No other vendor approaches this volume of systematic underreporting.",
        "context": "Field/text conflicts: vendor-004 (20+ rows), vendor-001/002/003/006/008 (1 row each). vendor-004 is the clear outlier in both volume and severity of contradictions.",
        "expected_behavior": "The agent should surface the conflict between the structured field (customer_impact) and the outcome text. It should not silently pick one signal. A good response notes the inconsistency and either recommends reconciliation or weights the more severe signal with justification.",
        "reference_facts": "vendor-004: 20+ systematic underreporting conflicts. Other vendors: 1 conflict row each. Ratio: vendor-004 represents ~80% of all field/text conflicts in the dataset.",
        "expected_failure_mode": "disambiguation_field_conflict",
    },
]

VALID_FAILURE_MODES = {
    "none_calibrated", "overconfidence_on_partial", "overconfidence_on_sparse",
    "missing_conflict_surface", "under_pattern_attribution", "over_pattern_attribution",
    "tool_output_refusal", "site_refusal",
    "disambiguation_unit_mismatch", "disambiguation_field_conflict", "disambiguation_vocabulary",
}


def gen_vendor_queries():
    queries = load_jsonl("datasets/vendor_queries.jsonl")
    existing_ids = {q["id"] for q in queries}

    new_rows = []
    for q in NEW_QUERIES:
        if q["id"] not in existing_ids:
            assert q["expected_failure_mode"] in VALID_FAILURE_MODES, \
                f"Invalid failure mode: {q['expected_failure_mode']}"
            new_rows.append(q)

    queries.extend(new_rows)
    save_jsonl("datasets/vendor_queries.jsonl", queries)
    print(f"vendor_queries.jsonl: {len(queries)} total rows ({len(new_rows)} added)")
    return queries


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    print("Generating data...")
    dispatches = gen_dispatches()
    outcomes = gen_incident_outcomes()
    comms = gen_communications()
    sla = gen_sla_records()
    queries = gen_vendor_queries()

    print("\n--- Summary ---")
    print(f"dispatches.json:        {len(dispatches)} rows")
    print(f"incident_outcomes.json: {len(outcomes)} rows")
    print(f"communications.json:    {len(comms)} rows")
    print(f"sla_records.json:       {len(sla)} rows")
    print(f"vendor_queries.jsonl:   {len(queries)} rows")

    # Validate counts
    assert 190 <= len(dispatches) <= 220, f"Dispatch count out of range: {len(dispatches)}"
    assert 95 <= len(outcomes) <= 110, f"Outcome count out of range: {len(outcomes)}"
    assert 105 <= len(queries) <= 115, f"Query count out of range: {len(queries)}"

    # Validate failure modes
    for q in queries:
        assert q["expected_failure_mode"] in VALID_FAILURE_MODES, \
            f"Invalid failure mode in {q['id']}: {q['expected_failure_mode']}"

    print("\nAll assertions passed.")
