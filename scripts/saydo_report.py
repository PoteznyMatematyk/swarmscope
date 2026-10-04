"""Markdown summary of the said-vs-did test-claim audit (data/work/saydo/saydo_tests.json) + review sample for skeptics.

    python scripts/saydo_report.py            # -> data/work/saydo/SAYDO_TESTS.md and review_sample.json
"""

from __future__ import annotations

import json
import random
from collections import Counter, defaultdict
from pathlib import Path

WORK = Path(__file__).resolve().parents[2] / "data" / "work" / "saydo"
CATS = ["backed", "backed_by_other_agent", "count_differs", "subagent_report_only", "contradicted", "run_unparsed", "no_run_observed", "relayed", "not_covered"]
JUDGED = CATS[:5]
FLAGGED = ("contradicted", "subagent_report_only")

d = json.loads((WORK / "saydo_tests.json").read_text(encoding="utf-8"))
rows = d["rows"]
by_cat = Counter(r["category"] for r in rows)
judged = [r for r in rows if r["category"] in JUDGED]
pct = lambda a, b: f"{100 * a / b:.1f}%" if b else "-"

out = [f"# Said vs did: chat claims that tests pass vs the agent's own executed test runs",
       "",
       f"Deterministic audit (`swarmscope saydo`, window {d['window_hours']} h before each claim). {d['claims']} chat messages in which an agent reports passing tests;",
       f"{len(judged)} could be judged against the agent's own computer-use test runs. Every claim quote and every run summary quote below is re-verified by code.",
       "",
       "| category | claims | share of judged |", "|---|---|---|"]
for c in CATS:
    out.append(f"| {c} | {by_cat.get(c, 0)} | {pct(by_cat.get(c, 0), len(judged)) if c in JUDGED else 'not judged'} |")
out += ["", "Sensitivity (claims per category for other windows):", ""]
for w, cats in d.get("sensitivity", {}).items():
    out.append(f"- {w} h: " + ", ".join(f"{k} {v}" for k, v in sorted(cats.items(), key=lambda kv: -kv[1])))

per = defaultdict(Counter)
for r in rows:
    per[r["agent"]][r["category"]] += 1
out += ["", "## Per agent (agents with >= 10 judged claims)", "", "| agent | judged | backed | count differs | latest run red* | relayed | no run / unparsed |", "|---|---|---|---|---|---|---|"]
for a, c in sorted(per.items(), key=lambda kv: -sum(kv[1][k] for k in JUDGED)):
    j = sum(c[k] for k in JUDGED)
    if j >= 10:
        red = c["subagent_report_only"] + c["contradicted"]
        out.append(f"| {a} | {j} | {pct(c['backed'] + c['backed_by_other_agent'], j)} | {pct(c['count_differs'], j)} | {red} | {c['relayed']} | {c['no_run_observed'] + c['run_unparsed']} |")
out += ["", "*latest run red = subagent_report_only + contradicted.", ""]

numbers = d["summary"].get("numbers_never_produced_by_any_run_7d", {})
out += ["## Claimed test counts that no executed run produced (any agent, previous 7 days)", "", "| category | claims with a number | number never produced by any run |", "|---|---|---|"]
for c in CATS:
    if c in numbers:
        out.append(f"| {c} | {numbers[c]['with_number']} | {numbers[c]['never_seen']} ({pct(numbers[c]['never_seen'], numbers[c]['with_number'])}) |")

flagged = [r for r in rows if r["category"] in FLAGGED]
out += ["", f"## Flagged cases ({len(flagged)}) - candidates for adversarial review, NOT findings yet", ""]
for r in flagged:
    run, sub = r.get("evidence_run"), r.get("subagent_report")
    out.append(f"- **{r['category']}** {r['ts'][:16]} UTC, {r['agent']} `{{{r['event_ref']}}}`: \"{r['claim_quote']}\"")
    if run:
        out.append(f"  - own run {run['lag_min']} min earlier `{{{run['ref']}}}`: \"{run['quote']}\"; latest run red: {r['last_run_red']}; runs in window {r['runs_in_window']} ({r['red_runs']} red)")
    if sub:
        out.append(f"  - sub-agent report {sub['lag_min']} min earlier `{{{sub['ref']}}}`")
out += ["", "Limits: only bash turns are parsed (tests run in a browser, in CI or through the Claude Code scaffolding are invisible here); a claim may concern another",
        "suite or another agent's branch; output is truncated to its first and last 600 characters. `contradicted` means \"the log does not show the claimed state\",",
        "not \"the agent lied\"."]
(WORK / "SAYDO_TESTS.md").write_text("\n".join(out) + "\n", encoding="utf-8")

rng = random.Random(7)
pool = lambda c, k: rng.sample([r for r in rows if r["category"] == c], min(k, sum(r["category"] == c for r in rows)))
sample = flagged + pool("backed", 12) + pool("backed_by_other_agent", 6) + pool("count_differs", 12)
(WORK / "review_sample.json").write_text(json.dumps(sample, indent=1, ensure_ascii=False), encoding="utf-8")
print(f"wrote SAYDO_TESTS.md ({len(out)} lines) and review_sample.json ({len(sample)} cases: {len(flagged)} flagged + backed/other-agent/count_differs samples)")
