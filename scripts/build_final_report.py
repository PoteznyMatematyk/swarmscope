"""Assemble the submission report from ACCEPTED work only, then embed it into the offline viewer.

    python scripts/build_final_report.py --runs claude flash --findings ../data/work/findings_final.json ../data/work/findings_final_E4.json --out ../data/work/final

Inputs
- data/work/runs/<dir>/ACCEPT_SWEEP.json (written by scripts/accept_all.py): only chunks with verdict ACCEPT are used
  (claims_v2 = final claims, claims_v1 = first pass, for the per-model misquote statistics);
- findings JSON (list): synthesized findings merged with reviewer verdicts; each may carry `survives`; only survivors are
  published unless --all-findings;
- said-vs-did cases (data/work/saydo/saydo_tests.json + optional review file) become one finding with event + turn evidence;
- tracer cascades for AI Village (optional).
Every quote is re-verified by build_report; nothing is trusted from the input files.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
WORK = ROOT / "data" / "work"
sys.path.insert(0, str(ROOT / "swarmscope" / "src"))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from swarmscope.report import build_report  # noqa: E402
from swarmscope.store import Store  # noqa: E402
from swarmscope.turns import open_turns  # noqa: E402


def accepted_batches(runs_dirs: list[str]) -> tuple[list[dict], list[dict], list[str]]:
    final, first, used = [], [], []
    seen: set[str] = set()  # a chunk analysed by two runs dirs is counted once: the first dir listed wins
    for d in runs_dirs:
        sweep = WORK / "runs" / d / "ACCEPT_SWEEP.json"
        if not sweep.exists():
            print(f"!! {sweep} missing: run scripts/accept_all.py {d} first")
            continue
        for row in json.loads(sweep.read_text(encoding="utf-8"))["rows"]:
            if row["verdict"] != "ACCEPT":
                continue
            if row["chunk"] in seen:
                print(f"note: {d}/{row['chunk']} skipped, the same chunk is already taken from an earlier runs dir")
                continue
            seen.add(row["chunk"])
            base = WORK / "runs" / d / row["chunk"]
            for lens_dir in sorted(p for p in base.iterdir() if p.is_dir()):
                v2, v1 = json.loads((lens_dir / "claims_v2.json").read_text(encoding="utf-8")), json.loads((lens_dir / "claims_v1.json").read_text(encoding="utf-8"))
                for b in (v2, v1):
                    b["chunk"] = f"{row['chunk']}/{lens_dir.name}"
                    b.setdefault("lens", lens_dir.name)
                final.append(v2)
                first.append(v1)
            used.append(f"{d}/{row['chunk']}")
    return final, first, used


def saydo_finding(review_path: Path | None) -> dict | None:
    """Confirmed said-vs-did cases (after skeptic review) as one finding; each case contributes its claim and its turn evidence."""
    if not review_path or not review_path.exists():
        return None
    review = json.loads(review_path.read_text(encoding="utf-8"))
    confirmed = [c for c in review.get("flagged", []) if c.get("verdict") == "confirmed"]
    if not confirmed:
        return None
    ev, did = [], []
    for c in confirmed:
        for e in c.get("evidence", []):
            (did if e.get("kind") == "turn" else ev).append({"ref": e["ref"], "quote": e["quote"], "role": "contradiction" if e.get("kind") == "turn" else "origin"})
    thesis = (f"Of the test-success claims that a deterministic audit could judge against the agent's own executed test runs, {len(confirmed)} survived a skeptical "
              "review of the log as cases where the agent reported passing tests although its own latest run was red or its only support was a coding sub-agent's report. "
              + " ".join(c["what_happened"].split(". ")[0].rstrip(".") + "." for c in confirmed))
    return {"id": "SAYDO-1", "title": "Test-success claims made against the agent's own latest test run",
            "thesis": thesis, "kind": "said_vs_did", "evidence": ev, "did_evidence": did,
            "limitations": ["only bash turns are parsed; CI and browser results are invisible", "a claim may concern another suite or branch",
                            "the audit's category 'count differs' has 25% precision in skeptic review and is not used as evidence"],
            "verdicts": [{"lens": "skeptic", "verdict": "accept", "one_line": c["what_happened"].split(". ")[0]} for c in confirmed],
            "survives": True}


def audit_meta() -> dict:
    """Semantic-audit numbers for the viewer's overview: all workflow audits (Claude analysts) and the Flash calibration audit, if present."""
    from audit_stats import audit_stats  # noqa: PLC0415

    s, out, other = audit_stats(), {}, []
    if "claude_first_rater" in s:
        f = s["claude_first_rater"]
        out["audit"] = {"sampled": f["claims"], **{k: f[k] for k in ("supported", "partially", "unsupported", "misleading")}}
        if s.get("claude_second_rater"):
            sec = s["claude_second_rater"]
            other.append({"label": "second Claude reviewer, same claims", "n": sec["claims"], "supported": sec["supported"]})
    if "codex" in s:
        c = s["codex"]
        other.append({"label": "GPT-6 Sol (Codex), other claims", "n": c["claims"], "supported": c["supported"]})
    cal = WORK / "runs" / "flash" / "audit_cal.json"
    if cal.exists():
        rows = json.loads(cal.read_text(encoding="utf-8"))
        other.append({"label": "Gemini 3.6 Flash High as analyst, one chunk", "n": len(rows), "supported": sum(r["verdict"] == "supported" for r in rows)})
    if other:
        out["audit_other"] = other
    return out


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--runs", nargs="+", default=["claude"])
    ap.add_argument("--findings", type=Path, nargs="+", help="one or more findings JSON files (findings_final.json, findings_final_E4.json, ...)")
    ap.add_argument("--all-findings", action="store_true")
    ap.add_argument("--saydo-review", type=Path, default=WORK / "saydo" / "saydo_review.json")
    ap.add_argument("--trace", type=Path)
    ap.add_argument("--title", default="SwarmScope: AI Village forensic battery")
    ap.add_argument("--out", type=Path, default=WORK / "final")
    args = ap.parse_args()

    store = Store(WORK / "snapshot.duckdb", read_only=True)
    turns_db = ROOT / "data" / "turns.duckdb"
    turns = open_turns(turns_db) if turns_db.exists() else None
    final, first, used = accepted_batches(args.runs)
    findings = [f for p in args.findings or [] for f in json.loads(p.read_text(encoding="utf-8"))]
    if not args.all_findings:
        findings = [f for f in findings if f.get("survives")]
    if (sf := saydo_finding(args.saydo_review)):
        findings.append(sf)
    day_map_p = ROOT / "data" / "day_map.json"
    report = build_report(store, meta={"title": args.title, "source": "ai_village", "chunks_used": used, **audit_meta()},
                          batches=final, first_pass=first, findings=findings,
                          cascades=json.loads(args.trace.read_text(encoding="utf-8")) if args.trace else None,
                          day_map=json.loads(day_map_p.read_text(encoding="utf-8")) if day_map_p.exists() else None, turns=turns)
    args.out.mkdir(parents=True, exist_ok=True)
    (args.out / "report.json").write_text(json.dumps(report, ensure_ascii=False, indent=1), encoding="utf-8")
    sys.path.insert(0, str(ROOT / "swarmscope" / "viewer"))
    import embed  # noqa: E402

    embed.main(["--report", str(args.out / "report.json"), "--out", str(args.out / "report.html")])
    m = report["metrics"]
    print(json.dumps({"chunks": len(used), "claims": len(report["claims"]), "findings": len(report["findings"]),
                      "final": m["final"], "first_pass_by_model": m.get("first_pass_by_model"), "tracer": m.get("tracer")}, ensure_ascii=False, indent=1))


if __name__ == "__main__":
    main()
