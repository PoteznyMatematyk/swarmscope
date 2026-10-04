"""Agreement between two independent semantic audits of the same claim samples (e.g. Claude reviewers vs another model family).

    python scripts/compare_audits.py            # Claude: runs/claude_synth/<ep>/audit_<k>.json, other: data/work/codex/out/audit_<ep>_<k>.json

Prints per-verdict counts for each auditor, raw agreement, agreement on the binary question "fully supported or not", Cohen's kappa
on that binary question, and every disagreement (with both one-line reasons). Writes data/work/audit_agreement.json.
"""

from __future__ import annotations

import collections
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
WORK = ROOT / "data" / "work"
VERDICTS = ("supported", "partially", "unsupported", "misleading")


def key(s: str) -> str:
    return re.sub(r"\s+", " ", s.strip())


def load(p: Path) -> dict[str, dict]:
    rows = json.loads(p.read_text(encoding="utf-8"))
    return {key(r["claim"]): r for r in rows}


def main() -> None:
    pairs = []
    for ep in ("E1_leader", "E2_saboteurs", "E4_tooler", "E5_outreach"):
        for k in (1, 2):
            a, b = WORK / "runs" / "claude_synth" / ep / f"audit_{k}.json", WORK / "codex" / "out" / f"audit_{ep}_{k}.json"
            if a.exists() and b.exists():
                pairs.append((ep, k, load(a), load(b)))
    rows, missing = [], 0
    for ep, k, ca, cb in pairs:
        for claim, ra in ca.items():
            rb = cb.get(claim)
            if rb is None:
                missing += 1
                continue
            rows.append({"sample": f"{ep}_{k}", "claim": claim, "claude": ra["verdict"], "other": rb["verdict"], "claude_reason": ra.get("reason", ""), "other_reason": rb.get("reason", "")})
    n = len(rows)
    if not n:
        print("no overlapping audits yet")
        return
    agree = sum(r["claude"] == r["other"] for r in rows)
    bc = [r["claude"] == "supported" for r in rows]
    bo = [r["other"] == "supported" for r in rows]
    po = sum(x == y for x, y in zip(bc, bo)) / n
    pc, pp = sum(bc) / n, sum(bo) / n
    pe = pc * pp + (1 - pc) * (1 - pp)
    kappa = (po - pe) / (1 - pe) if pe < 1 else 1.0
    cnt = {who: collections.Counter(r[who] for r in rows) for who in ("claude", "other")}
    print(f"{n} claims audited by both ({missing} not found in the other audit)")
    for who in ("claude", "other"):
        print(f"  {who:<7} " + ", ".join(f"{v} {cnt[who][v]}" for v in VERDICTS) + f"  -> fully supported {pct(cnt[who]['supported'], n)}")
    print(f"  identical verdict: {agree}/{n} ({pct(agree, n)}); same answer to 'fully supported?': {pct(round(po * n), n)}; Cohen's kappa (binary) {kappa:.2f}")
    worst = collections.Counter((r["claude"], r["other"]) for r in rows if r["claude"] != r["other"])
    print("  disagreements (claude -> other):", dict(worst))
    for r in rows:
        if (r["claude"] == "supported") != (r["other"] == "supported"):
            print(f"\n[{r['sample']}] {r['claim']}\n   claude {r['claude']}: {r['claude_reason'][:200]}\n   other  {r['other']}: {r['other_reason'][:200]}")
    (WORK / "audit_agreement.json").write_text(json.dumps({"n": n, "identical": agree, "binary_agreement": po, "kappa": kappa, "claude": dict(cnt["claude"]), "other": dict(cnt["other"]), "rows": rows}, ensure_ascii=False, indent=1), encoding="utf-8")


def pct(a: int, b: int) -> str:
    return f"{100 * a / b:.0f}%"


if __name__ == "__main__":
    main()
