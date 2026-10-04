"""Headline numbers for the README, write-up and video, computed from the work files (never typed by hand).

    python scripts/report_numbers.py [--report data/work/final/report.json] [--runs claude flash] [--out data/work/numbers.json]

Sources: runs/<dir>/ACCEPT_SWEEP.json (independent gate), windows/manifest.json (events per chunk), the report (quote integrity, first-pass
misquote rate per model), workflow_result_*.json (semantic audits), findings_final*.json (survivors and claim checks), saydo/saydo_tests.json.
"""

from __future__ import annotations

import argparse
import collections
import glob
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
WORK = ROOT / "data" / "work"


def load(p: Path):
    return json.loads(p.read_text(encoding="utf-8"))


def pct(a: int, b: int) -> str:
    return f"{100 * a / b:.0f}%" if b else "n/a"


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--report", type=Path, default=WORK / "final" / "report.json")
    ap.add_argument("--runs", nargs="+", default=["claude", "flash"])
    ap.add_argument("--out", type=Path, default=WORK / "numbers.json")
    args = ap.parse_args()
    manifest = load(WORK / "windows" / "manifest.json")
    N: dict = {}

    # coverage: chunks that the independent gate accepted
    cov = collections.defaultdict(lambda: {"chunks": 0, "events": 0, "claims": 0})
    seen: set[str] = set()  # same rule as build_final_report.py: a chunk analysed by two runs dirs counts once (first dir listed)
    for d in args.runs:
        sweep = WORK / "runs" / d / "ACCEPT_SWEEP.json"
        if not sweep.exists():
            continue
        for row in load(sweep)["rows"]:
            if row["verdict"] != "ACCEPT" or row["chunk"] in seen:
                continue
            seen.add(row["chunk"])
            ep, _, idx = row["chunk"].rpartition("_c")
            c = cov[ep]
            c["chunks"] += 1
            c["events"] += manifest[ep]["chunks"][int(idx) - 1]["events"]
            c["claims"] += row["claims_v2"]
    N["coverage"] = dict(cov)
    N["totals"] = {k: sum(v[k] for v in cov.values()) for k in ("chunks", "events", "claims")}

    # quote integrity
    if args.report.exists():
        m = load(args.report)["metrics"]
        N["quotes_final"] = m["final"]
        N["quotes_first_pass"] = m.get("first_pass")
        N["first_pass_by_model"] = m.get("first_pass_by_model")

    # semantic audits (verified quote -> supported claim?)
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    from audit_stats import audit_stats  # noqa: PLC0415

    N["audit"] = audit_stats()

    # Flash calibration (gate ACCEPT, then the same semantic audit; decision rule fixed beforehand: go if >= 75% supported)
    cal = WORK / "runs" / "flash" / "audit_cal.json"
    if cal.exists():
        rows = load(cal)
        c = collections.Counter(r["verdict"] for r in rows)
        N["audit_flash_calibration"] = {"n": len(rows), **dict(c), "supported_share": round(c["supported"] / len(rows), 3)}

    # findings
    findings =[f for p in sorted(glob.glob(str(WORK / "findings_final*.json"))) if "before_retitle" not in p for f in load(Path(p))]
    if findings:
        checks = collections.Counter(c.get("status") for f in findings for c in (f.get("rereview") or {}).get("claim_checks", []))
        N["findings"] = {"reviewed": len(findings), "survive": sum(bool(f.get("survives")) for f in findings),
                         "by_episode": dict(collections.Counter(f["episode"] for f in findings if f.get("survives"))),
                         "claim_checks": dict(checks), "claim_checks_total": sum(checks.values()),
                         "first_round_accepts": collections.Counter(f.get("accepts") for f in findings).most_common()}

    # said vs did
    sd = WORK / "saydo" / "saydo_tests.json"
    if sd.exists():
        s = load(sd)["summary"]
        N["saydo"] = {"claims": load(sd)["claims"], "judged": s["judged"], "by_category": s["by_category"], "backed_share": s["backed_share_of_judged"]}

    args.out.write_text(json.dumps(N, ensure_ascii=False, indent=1), encoding="utf-8")
    t = N["totals"]
    print(f"coverage: {t['chunks']} chunks ACCEPT, {t['events']:,} events read in full, {t['claims']:,} claims")
    for ep, c in sorted(cov.items()):
        print(f"   {ep:<18} {c['chunks']:>2} chunks {c['events']:>6,} events {c['claims']:>5} claims")
    if "quotes_final" in N:
        q, fp = N["quotes_final"], N.get("quotes_first_pass") or {}
        print(f"quotes: {q['quote_status'].get('verified', 0):,}/{q['quotes']:,} verified in the report; first pass {fp.get('quote_reject_rate')} rejected")
        for mdl, v in (N.get("first_pass_by_model") or {}).items():
            print(f"   first-pass misquote rate {mdl}: {v['reject_rate']} ({v['verified']}/{v['quotes']} ok)")
    a = N.get("audit", {})
    if "claude" in a:
        c = a["claude"]
        print(f"semantic audit, Claude reviewers: {c['claims']} distinct claims, {c['verdicts']} verdicts, supported {c['supported']} ({pct(c['supported'], c['verdicts'])}), partially {c['partially']}, "
              f"unsupported {c['unsupported']}, misleading {c['misleading']}; two raters agree on {c['raters_identical']}/{c['claims_with_two_raters']}, both 'supported' on {c['both_supported']}")
    if "codex" in a:
        c = a["codex"]
        print(f"semantic audit, GPT-6 Sol (Codex): {c['claims']} claims, supported {c['supported']} ({pct(c['supported'], c['claims'])}), partially {c['partially']}, unsupported {c['unsupported']}, misleading {c['misleading']}")
    if "cross" in a:
        c = a["cross"]
        print(f"cross-family: {c['claims']} claims judged by both; identical verdict {c['identical']}/{c['pairs']}, binary agreement {c['binary_agreement']}, kappa {c['kappa']}")
    print(f"distinct claims audited by at least one auditor: {a.get('distinct_claims_audited')}")
    if "findings" in N:
        f = N["findings"]
        cc = f["claim_checks"]
        print(f"findings: {f['reviewed']} reviewed, {f['survive']} survive {f['by_episode']}; re-verified factual claims: "
              + ", ".join(f"{k} {v} ({pct(v, f['claim_checks_total'])})" for k, v in cc.items()))
    if "saydo" in N:
        s = N["saydo"]
        print(f"said vs did: {s['claims']} claims, {s['judged']} judged, backed {s['backed_share']:.1%}; categories {s['by_category']}")


if __name__ == "__main__":
    main()
