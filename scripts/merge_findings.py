"""Merge a finished battery_v2 workflow result (reviewer verdicts) with the full synthesized findings (evidence, counter-evidence).

    python scripts/save_workflow_result.py <task .output file> data/work/workflow_result.json
    python scripts/merge_findings.py data/work/workflow_result.json [data/work/findings_reviewed.json]

Output: a list of findings ready for `build_final_report.py`: original synthesized fields + `episode`, `verdicts`, `accepts`, `survives`
and `corrected_thesis` (the support reviewer's wording when it asked for a revision; NOT substituted automatically because the
evidence list was collected for the original thesis - choosing the published wording is an editorial step).
"""

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
WORK = ROOT / "data" / "work"
res = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
out_path = Path(sys.argv[2]) if len(sys.argv) > 2 else WORK / "findings_reviewed.json"
merged = []
for ep in res["episodes"]:
    cand_path = WORK / "runs" / "claude_synth" / ep["name"] / "findings_candidates.json"
    if not cand_path.exists():
        continue
    by_id = {f["id"]: f for f in json.loads(cand_path.read_text(encoding="utf-8"))}
    for f in ep.get("findings", []):
        full = dict(by_id.get(f["id"], {k: f[k] for k in ("id", "title", "thesis", "importance")}))
        support = next((v for v in f["verdicts"] if v.get("lens") == "support"), {})
        full.update(episode=ep["name"], verdicts=f["verdicts"], accepts=f["accepts"], survives=f["survives"],
                    corrected_thesis=support.get("corrected_thesis") or None)
        merged.append(full)
out_path.parent.mkdir(parents=True, exist_ok=True)
out_path.write_text(json.dumps(merged, ensure_ascii=False, indent=1), encoding="utf-8")
print(f"{len(merged)} findings -> {out_path}; survive: {sum(f['survives'] for f in merged)}")
for f in merged:
    lens = " ".join(f"{v['lens'][:3]}={v['verdict'][:3]}" for v in f["verdicts"])
    print(f"{f['id']:<20} {'SURVIVES' if f['survives'] else 'dropped ':<9} imp={f.get('importance')} accepts={f['accepts']} [{lens}] {f['title'][:90]}")
audits = [(ep["name"], a) for ep in res["episodes"] for a in ep.get("audits", [])]
if audits:
    n = sum(a["n"] for _, a in audits)
    sup = sum(a["supported"] for _, a in audits)
    par = sum(a["partially"] for _, a in audits)
    print(f"semantic audit: {n} claims sampled; supported {sup} ({100 * sup / n:.0f}%), partially {par}, "
          f"unsupported {sum(a['unsupported'] for _, a in audits)}, misleading {sum(a['misleading'] for _, a in audits)}")
