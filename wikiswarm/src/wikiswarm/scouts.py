"""Scouts: agents that say they fast-forwarded their own task clock. Do they account for more of the first
reveals than their share of activity?

Inputs: work/audit/scout_labels.jsonl (labels by a second model, quotes machine-checked here),
work/audit/scout_records.jsonl, work/metrics.json, work/foreknowledge.json, work/tuples_verified.jsonl.

    python -m wikiswarm.scouts
Writes work/scouts.json.
"""
from __future__ import annotations

import json
import sys
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from gate.common import FIRST_HAND, norm_item, norm_time, read_jsonl, write_json, ws  # noqa: E402

WORK = ROOT / "work"


def main() -> None:
    texts = {r["scout_id"]: r for r in read_jsonl(WORK / "audit" / "scout_records.jsonl")}
    labels = list(read_jsonl(WORK / "audit" / "scout_labels.jsonl"))
    bad_quote = 0
    ok = []
    for lab in labels:
        rec = texts.get(lab.get("scout_id"))
        q = lab.get("quote") or ""
        flags = [lab.get(k) is True for k in ("self_accelerates", "asks_others", "for_relay", "accepts_cost")]
        if not any(flags):
            continue
        if rec is None or not q or ws(q) not in ws(rec["text"]):
            bad_quote += 1
            continue
        ok.append({**lab, "wall_time": norm_time(rec["wall_time"]), "page_family": rec["page_family"]})

    scouts = {lab["signer"] for lab in ok if lab["self_accelerates"] and lab.get("signer")}
    askers = {lab["signer"] for lab in ok if lab["asks_others"] and lab.get("signer")}
    counts = {k: sum(1 for lab in ok if lab[k]) for k in ("self_accelerates", "asks_others", "for_relay", "accepts_cost")}

    metrics = json.loads((WORK / "metrics.json").read_text(encoding="utf-8"))
    fk = json.loads((WORK / "foreknowledge.json").read_text(encoding="utf-8"))
    tuples = [t for t in read_jsonl(WORK / "tuples_verified.jsonl") if norm_time(t.get("wall_time"))]

    # 1. answer reveals per unit (who first posted the consensus answer)
    reveal_sigs = [u["revealer"] for u in metrics["units"] if u["revealer"]]
    # 2. first mention of each unit's item by anyone (who first put the question on the wiki)
    unit_keys = {(u["family"], u["round"], u["item"]) for u in metrics["units"]}
    first = {}
    for t in sorted(tuples, key=lambda t: (norm_time(t["wall_time"]), t["record_id"])):
        if t["round"] is None or not t["signature"]:
            continue
        k = (t["family"], t["round"], norm_item(t["item"]))
        if k in unit_keys and k not in first:
            first[k] = t["signature"]
    first_sigs = list(first.values())
    # 3. the 'another agent first' side of each foreknowledge case
    fk_sources = [c["earlier_other"]["signature"] for c in fk["cases"] if c["earlier_other"] and c["earlier_other"]["signature"]]
    # baseline: share of all signed statements in the same families
    fams = {u["family"] for u in metrics["units"]}
    stmt = Counter(t["signature"] for t in tuples if t["signature"] and t["family"] in fams)
    active = set(stmt)

    def share(sigs):
        return {"n": len(sigs), "by_scouts": sum(1 for s in sigs if s in scouts),
                "share": round(sum(1 for s in sigs if s in scouts) / len(sigs), 4) if sigs else None}

    out = {
        "labels": len(labels), "labels_with_flag_and_verified_quote": len(ok), "labels_quote_not_found": bad_quote,
        "label_counts": counts,
        "scout_signatures": len(scouts), "asking_signatures": len(askers),
        "active_signatures_in_unit_families": len(active),
        "scouts_among_active": len(scouts & active),
        "baseline_statements": {"n": sum(stmt.values()), "by_scouts": sum(c for s, c in stmt.items() if s in scouts),
                                "share": round(sum(c for s, c in stmt.items() if s in scouts) / sum(stmt.values()), 4)},
        "answer_reveals": share(reveal_sigs),
        "first_mentions": share(first_sigs),
        "foreknowledge_sources": share(fk_sources),
        "examples": [{k: lab[k] for k in ("signer", "wall_time", "quote", "self_accelerates", "asks_others", "for_relay", "accepts_cost")}
                     for lab in sorted(ok, key=lambda x: x["wall_time"]) if lab["self_accelerates"] and lab["for_relay"]][:8],
        "accepts_cost_examples": [{k: lab[k] for k in ("signer", "wall_time", "quote")}
                                  for lab in sorted(ok, key=lambda x: x["wall_time"]) if lab["accepts_cost"]][:6],
    }
    write_json(WORK / "scouts.json", out)
    print(json.dumps({k: out[k] for k in out if k not in ("examples", "accepts_cost_examples")}, indent=1))


if __name__ == "__main__":
    main()
