"""Metrics aggregation for wikiswarm: exposure, lead time, scouts, and misinformation."""
from __future__ import annotations

import argparse
import json
import statistics
import sys
from collections import Counter, defaultdict
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from gate.common import FIRST_HAND, digits, norm_item, norm_time, read_jsonl, write_json  # noqa: E402


def _t(s: str) -> datetime:
    return datetime.fromisoformat(s.replace("Z", "+00:00"))


def _minutes(a: str, b: str) -> float:
    return round((_t(b) - _t(a)).total_seconds() / 60.0, 4)


def aggregate(tuples: list[dict]) -> dict:
    rows = []
    no_time = 0
    for t in tuples:
        wt = norm_time(t.get("wall_time"))
        if not wt:  # posts without a recoverable time cannot be ordered
            no_time += 1
            continue
        r = dict(t, wall_time=wt)
        r["nitem"] = norm_item(t["item"])
        r["nvalue"] = digits(t.get("value")) or None
        rows.append(r)

    # 1. units = (family, round, nitem) with >= 2 distinct signatures among first-hand, round-stamped tuples
    fh_sigs = defaultdict(set)
    for r in rows:
        if r["kind"] in FIRST_HAND and r["round"] is not None and r["signature"]:
            fh_sigs[(r["family"], r["round"], r["nitem"])].add(r["signature"])
    units = {k for k, s in fh_sigs.items() if len(s) >= 2}

    # 2. null-round tuples: assign a round when the item matches exactly one unit of the family
    by_fam_item = defaultdict(set)
    for (f, k, i) in units:
        by_fam_item[(f, i)].add(k)
    null_dropped = 0
    for r in rows:
        if r["round"] is None:
            ks = by_fam_item.get((r["family"], r["nitem"]), set())
            if len(ks) == 1:
                r["round"] = next(iter(ks))
            else:
                null_dropped += 1

    unit_rows = defaultdict(list)
    for r in rows:
        if r["round"] is not None:
            unit_rows[(r["family"], r["round"], r["nitem"])].append(r)

    receiver_rounds = exposed = confirmed = 0
    leads: list[float] = []
    revealers: Counter = Counter()
    wrong_values = []
    unit_out = []
    for u in sorted(units):
        rs = sorted(unit_rows[u], key=lambda r: (r["wall_time"], r["record_id"]))
        fh = [r for r in rs if r["kind"] in FIRST_HAND]
        # consensus value: most distinct signatures among first-hand tuples with a value; tie -> earliest
        val_sigs: dict[str, set] = defaultdict(set)
        val_first: dict[str, str] = {}
        for r in fh:
            if r["nvalue"] and r["signature"]:
                val_sigs[r["nvalue"]].add(r["signature"])
                val_first.setdefault(r["nvalue"], r["wall_time"])
        cval = None
        if val_sigs:
            cval = sorted(val_sigs, key=lambda v: (-len(val_sigs[v]), val_first[v]))[0]
        # reveal: earliest first-hand or relayed tuple carrying the consensus value (any signature, may be None)
        reveal = None
        if cval:
            for r in rs:
                if r["kind"] in FIRST_HAND | {"relayed"} and r["nvalue"] == cval:
                    reveal = r
                    break
        if reveal and reveal["signature"]:
            revealers[reveal["signature"]] += 1
        # receivers: signatures (not the revealer) with a first-hand tuple; their earliest such tuple
        first_fh: dict[str, dict] = {}
        for r in fh:
            if r["signature"] and r["signature"] not in first_fh:
                first_fh[r["signature"]] = r
        rev_sig = reveal["signature"] if reveal else None
        n_recv = n_exp = n_conf = 0
        for sig, r in first_fh.items():
            if sig == rev_sig:
                continue
            n_recv += 1
            if reveal and reveal.get("wall_time") and r.get("wall_time") and r["wall_time"] > reveal["wall_time"]:
                n_exp += 1
                leads.append(_minutes(reveal["wall_time"], r["wall_time"]))
                if any(x["used_cache"] for x in fh if x["signature"] == sig):
                    n_conf += 1
        receiver_rounds += n_recv
        exposed += n_exp
        confirmed += n_conf
        # wrong values: other values on this unit among first-hand + relayed tuples
        other = defaultdict(set)
        for r in rs:
            if r["kind"] in FIRST_HAND | {"relayed"} and r["nvalue"] and r["nvalue"] != cval and r["signature"]:
                other[r["nvalue"]].add(r["signature"])
        for v, s in sorted(other.items()):
            wrong_values.append({"family": u[0], "round": u[1], "item": u[2], "value": v, "n_signatures": len(s)})
        unit_out.append({"family": u[0], "round": u[1], "item": u[2], "consensus_value": cval,
                         "n_first_hand_signatures": len(fh_sigs[u]),
                         "reveal_time": reveal["wall_time"] if reveal else None,
                         "revealer": rev_sig, "receivers": n_recv, "exposed": n_exp, "confirmed_use": n_conf})

    # wrong predictions: predicted (family, round, item) that is not a unit while a unit exists at (family, round)
    unit_rounds = {(f, k) for (f, k, _) in units}
    pred = defaultdict(lambda: {"sigs": set(), "first": None, "values": set()})
    for r in rows:
        if r["kind"] == "predicted" and r["round"] is not None:
            key = (r["family"], r["round"], r["nitem"])
            if key not in units and (r["family"], r["round"]) in unit_rounds:
                p = pred[key]
                if r["signature"]:
                    p["sigs"].add(r["signature"])
                if r["nvalue"]:
                    p["values"].add(r["nvalue"])
                times = [t for t in (p["first"], r.get("wall_time")) if t]
                if times:
                    p["first"] = min(times)
    wrong_predictions = [{"family": f, "round": k, "item": i, "values": sorted(p["values"]),
                          "n_signatures": len(p["sigs"]), "first_time": p["first"]}
                         for (f, k, i), p in sorted(pred.items())]

    top5 = sum(c for _, c in revealers.most_common(5))
    return {
        "n_tuples": len(rows),
        "n_units": len(units),
        "n_units_by_family": dict(sorted(Counter(f for f, _, _ in units).items())),
        "null_round_dropped": null_dropped,
        "no_time_dropped": no_time,
        "receiver_rounds": receiver_rounds,
        "exposed_upper": exposed,
        "exposed_upper_share": round(exposed / receiver_rounds, 4) if receiver_rounds else None,
        "confirmed_use": confirmed,
        "confirmed_use_share": round(confirmed / receiver_rounds, 4) if receiver_rounds else None,
        "lead_minutes_median": statistics.median(leads) if leads else None,
        "revealers": dict(sorted(revealers.items())),
        "top5_revealer_share": round(top5 / sum(revealers.values()), 4) if revealers else None,
        "wrong_values": wrong_values,
        "wrong_predictions": wrong_predictions,
        "units": unit_out,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Aggregate wikiswarm metrics")
    parser.add_argument("--tuples", required=True, type=Path, help="Path to input tuples JSONL")
    parser.add_argument("--out", required=True, type=Path, help="Path to output metrics JSON")
    args = parser.parse_args()

    tuples = list(read_jsonl(args.tuples))
    metrics = aggregate(tuples)
    write_json(args.out, metrics)
    print(f"Aggregated {len(tuples)} tuples into {metrics['n_units']} units -> {args.out}")


if __name__ == "__main__":
    main()
