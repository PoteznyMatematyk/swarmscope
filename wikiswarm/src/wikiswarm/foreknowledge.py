"""Foreknowledge: did an agent name a round's question (and answer) in an earlier post, before it reported
receiving that round itself, and had another agent already put that item on the wiki?

This replaces the timing-only 'exposed' measure with evidence written by the agent itself: two verified
quotes from the same signature, in two different posts, in the right order.

    python -m wikiswarm.foreknowledge --tuples work/tuples_verified.jsonl --metrics work/metrics.json --out work/foreknowledge.json
"""
from __future__ import annotations

import argparse
import json
import sys
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from gate.common import FIRST_HAND, digits, norm_item, norm_time, read_jsonl, write_json  # noqa: E402

AHEAD = {"predicted", "relayed"}


def compute(tuples: list[dict], units: list[dict]) -> dict:
    unit_set = {(u["family"], u["round"], u["item"]) for u in units}
    cval = {(u["family"], u["round"], u["item"]): u["consensus_value"] for u in units}
    rounds_of = defaultdict(set)
    for f, k, i in unit_set:
        rounds_of[(f, i)].add(k)

    rows = []
    for t in tuples:
        wt = norm_time(t.get("wall_time"))
        if not wt:
            continue
        r = dict(t, wall_time=wt, nitem=norm_item(t["item"]), nvalue=digits(t.get("value")) or None)
        if r["round"] is None:
            ks = rounds_of.get((r["family"], r["nitem"]), set())
            if len(ks) != 1:
                continue
            r["round"] = next(iter(ks))
        if (r["family"], r["round"], r["nitem"]) in unit_set:
            rows.append(r)
    rows.sort(key=lambda r: (r["wall_time"], r["record_id"]))

    by_unit = defaultdict(list)
    for r in rows:
        by_unit[(r["family"], r["round"], r["nitem"])].append(r)

    out_units, cases = [], []
    tot = dict(receivers=0, posted_ahead=0, item_ahead=0, value_ahead=0, item_ahead_after_other=0)
    for key in sorted(unit_set):
        rs = by_unit[key]
        first_fh = {}
        for r in rs:
            if r["kind"] in FIRST_HAND and r["signature"] and r["signature"] not in first_fh:
                first_fh[r["signature"]] = r
        u = dict(receivers=0, item_ahead=0, value_ahead=0, item_ahead_after_other=0)
        for sig, fh in first_fh.items():
            u["receivers"] += 1
            ahead = [r for r in rs if r["signature"] == sig and r["kind"] in AHEAD
                     and r["wall_time"] < fh["wall_time"] and r["record_id"] != fh["record_id"]]
            if not ahead:
                continue
            first = ahead[0]
            u["item_ahead"] += 1
            with_value = [r for r in ahead if r["nvalue"] and r["nvalue"] == cval[key]]
            if with_value:
                u["value_ahead"] += 1
            other_before = [r for r in rs if r["signature"] and r["signature"] != sig
                            and r["wall_time"] < first["wall_time"]]
            if other_before:
                u["item_ahead_after_other"] += 1
            cases.append({
                "family": key[0], "round": key[1], "item": key[2], "signature": sig,
                "ahead": {k: first[k] for k in ("record_id", "wall_time", "kind", "quote")},
                "ahead_with_value": bool(with_value),
                "own_report": {k: fh[k] for k in ("record_id", "wall_time", "kind", "quote")},
                "earlier_other": ({k: other_before[0][k] for k in ("record_id", "wall_time", "signature", "quote")}
                                  if other_before else None),
            })
        for k in u:
            tot[k] += u[k]
        out_units.append({"family": key[0], "round": key[1], "item": key[2], **u})

    # how many receivers posted anything in the same family before their first-hand report (denominator check)
    fam_posts = defaultdict(list)
    for t in tuples:
        if norm_time(t.get("wall_time")) and t["signature"]:
            fam_posts[(t["family"], t["signature"])].append(norm_time(t["wall_time"]))
    posted_ahead = 0
    for key in sorted(unit_set):
        for r in by_unit[key]:
            pass
    seen = set()
    for key in sorted(unit_set):
        for r in by_unit[key]:
            if r["kind"] in FIRST_HAND and r["signature"] and (key, r["signature"]) not in seen:
                seen.add((key, r["signature"]))
                if any(w < r["wall_time"] for w in fam_posts[(key[0], r["signature"])]):
                    posted_ahead += 1
    tot["posted_ahead"] = posted_ahead
    return {"totals": tot, "units": out_units, "cases": cases}


def main() -> None:
    a = argparse.ArgumentParser()
    a.add_argument("--tuples", default=str(ROOT / "work" / "tuples_verified.jsonl"))
    a.add_argument("--metrics", default=str(ROOT / "work" / "metrics.json"))
    a.add_argument("--out", default=str(ROOT / "work" / "foreknowledge.json"))
    n = a.parse_args()
    units = json.loads(Path(n.metrics).read_text(encoding="utf-8"))["units"]
    res = compute(list(read_jsonl(Path(n.tuples))), units)
    write_json(Path(n.out), res)
    print(json.dumps(res["totals"]))


if __name__ == "__main__":
    main()
