"""Merge the reconcile outputs of a battery_v2 workflow run into publishable findings and re-verify every quote with code.

    python scripts/save_workflow_result.py <task .output file> data/work/workflow_result_E4.json
    python scripts/merge_final.py data/work/workflow_result_E4.json data/work/findings_final_E4.json [--runs-dir claude]

For every reviewed finding the workflow left runs/<runs-dir>_synth/<episode>/final_<id>.json (a list holding the reconciler's object).
The merged item keeps the candidate's structure (kind, actors, window, importance, ...) and carries: title/thesis = the reconciler's final
version, original_title/original_thesis, rereview = {verdict, caveats, claim_checks}, verdicts (the four lens reviewers), quote_check.

A finding survives only if (1) the workflow says so (reconciler verdict != reject and the `did` reviewer did not reject) AND (2) every quote in its
evidence, counter-evidence and did_evidence verifies against the log / the turns database. Nothing an agent reports about itself is trusted.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
WORK = ROOT / "data" / "work"
sys.path.insert(0, str(ROOT / "swarmscope" / "src"))

from swarmscope.evidence import verify_citation  # noqa: E402
from swarmscope.store import Store  # noqa: E402
from swarmscope.turns import open_turns, verify_turn_quote  # noqa: E402


def failing_quotes(store: Store, turns, f: dict) -> tuple[int, list[str]]:
    checked, bad = 0, []
    for key in ("evidence", "counter_evidence"):
        for e in f.get(key) or []:
            checked += 1
            status = verify_citation(store, str(e.get("ref", "")), str(e.get("quote", ""))).status
            if status != "verified":
                bad.append(f"{key}:{e.get('ref')}:{status}")
    for e in f.get("did_evidence") or []:
        checked += 1
        status = verify_turn_quote(turns, str(e.get("ref", "")), str(e.get("quote", ""))) if turns is not None else "no_turns_db"
        if status != "verified":
            bad.append(f"did_evidence:{e.get('ref')}:{status}")
    return checked, bad


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("result", type=Path, help="workflow result JSON (save_workflow_result.py)")
    ap.add_argument("out", type=Path, nargs="?", default=WORK / "findings_final_new.json")
    ap.add_argument("--runs-dir", default="claude")
    args = ap.parse_args()

    res = json.loads(args.result.read_text(encoding="utf-8"))
    store = Store(WORK / "snapshot.duckdb", read_only=True)
    turns_db = ROOT / "data" / "turns.duckdb"
    turns = open_turns(turns_db) if turns_db.exists() else None
    merged: list[dict] = []
    for ep in res["episodes"]:
        synth = WORK / "runs" / f"{args.runs_dir}_synth" / ep["name"]
        cand_p = synth / "findings_candidates.json"
        cands = {c["id"]: c for c in json.loads(cand_p.read_text(encoding="utf-8"))} if cand_p.exists() else {}
        for f in ep.get("findings", []):
            base = dict(cands.get(f["id"], {k: f[k] for k in ("id", "title", "thesis", "importance")}))
            item = {**base, "episode": ep["name"], "verdicts": f.get("verdicts", []), "accepts": f.get("accepts"),
                    "original_title": base.get("title"), "original_thesis": base.get("thesis"),
                    "strict_survives": f.get("strict_survives")}
            final_p = synth / f"final_{f['id']}.json"
            if not final_p.exists() or not f.get("reconcile"):
                merged.append({**item, "survives": False, "drop_reason": "no reconcile output"})
                continue
            fin = json.loads(final_p.read_text(encoding="utf-8"))
            fin = fin[0] if isinstance(fin, list) else fin
            caveats = fin.get("remaining_caveats") or []
            item.update(title=fin.get("final_title") or base.get("title"), thesis=fin.get("final_thesis") or base.get("thesis"),
                        evidence=fin.get("evidence") or [], counter_evidence=fin.get("counter_evidence") or [],
                        did_evidence=fin.get("did_evidence") or [], limitations=caveats,
                        rereview={"verdict": fin.get("verdict"), "caveats": caveats, "claim_checks": fin.get("claim_checks") or []},
                        reconcile_one_line=fin.get("one_line"))
            checked, bad = failing_quotes(store, turns, item)
            item["quote_check"] = {"checked": checked, "failing": bad}
            item["survives"] = bool(f.get("survives")) and fin.get("verdict") != "reject" and not bad and checked > 0
            if not item["survives"]:
                item["drop_reason"] = ("reconciler rejected" if fin.get("verdict") == "reject" else "workflow rule (did-lens reject or missing reconcile)"
                                       if not f.get("survives") else f"unverified quotes: {bad[:3]}")
            merged.append(item)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(merged, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"{len(merged)} findings -> {args.out}; survive: {sum(bool(m['survives']) for m in merged)}")
    for m in merged:
        lens = " ".join(f"{v['lens'][:3]}={v['verdict'][:3]}" for v in m["verdicts"])
        qc = m.get("quote_check", {})
        print(f"{m['id']:<20} {'SURVIVES' if m['survives'] else 'dropped ':<9} {(m.get('rereview') or {}).get('verdict', '-'):<7} "
              f"imp={m.get('importance')} quotes {qc.get('checked', 0) - len(qc.get('failing', []))}/{qc.get('checked', 0)} [{lens}] {str(m.get('title'))[:80]}")
    audits = [a for ep in res["episodes"] for a in ep.get("audits", [])]
    if audits:
        n = sum(a["n"] for a in audits)
        print(f"semantic audit: {n} claims sampled; supported {sum(a['supported'] for a in audits)} ({100 * sum(a['supported'] for a in audits) / n:.0f}%), "
              f"partially {sum(a['partially'] for a in audits)}, unsupported {sum(a['unsupported'] for a in audits)}, misleading {sum(a['misleading'] for a in audits)}")


if __name__ == "__main__":
    main()
