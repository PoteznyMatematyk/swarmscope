"""Semantic-audit statistics over distinct claims, from every auditor's files.

    python scripts/audit_stats.py

Auditors: Claude reviewers (data/work/runs/claude_synth/<episode>/audit_<k>.json, two per episode, which turned out to have judged the SAME claims, so
they count as two raters of one sample) and Codex / GPT-6 Sol (data/work/codex/out/audit_*.json: the same claims plus fresh ones). Each verdict is
supported | partially | unsupported | misleading for "does the quote, in context, really support the claim".
"""

from __future__ import annotations

import collections
import glob
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
WORK = ROOT / "data" / "work"
V = ("supported", "partially", "unsupported", "misleading")


def key(s: str) -> str:
    return re.sub(r"\s+", " ", s.strip())


def _load(p: str) -> list[dict]:
    return json.loads(Path(p).read_text(encoding="utf-8"))


def kappa_binary(pairs: list[tuple[bool, bool]]) -> float:
    n = len(pairs)
    po = sum(a == b for a, b in pairs) / n
    pa, pb = sum(a for a, _ in pairs) / n, sum(b for _, b in pairs) / n
    pe = pa * pb + (1 - pa) * (1 - pb)
    return (po - pe) / (1 - pe) if pe < 1 else 1.0


def audit_stats() -> dict:
    claude: dict[str, list[str]] = collections.defaultdict(list)
    for p in sorted(glob.glob(str(WORK / "runs" / "claude_synth" / "*" / "audit_*.json"))):
        for r in _load(p):
            claude[key(r["claim"])].append(r["verdict"])
    codex: dict[str, str] = {}
    for p in sorted(glob.glob(str(WORK / "codex" / "out" / "audit_*.json"))):
        if "offset0_other_sample" in p:
            continue
        for r in _load(p):
            codex.setdefault(key(r["claim"]), r["verdict"])
    out: dict = {}
    if claude:
        allv = [v for vs in claude.values() for v in vs]
        two = [vs for vs in claude.values() if len(vs) >= 2]
        first = [vs[0] for vs in claude.values()]
        out["claude_first_rater"] = {"claims": len(first), **{k: first.count(k) for k in V}}
        out["claude_second_rater"] = {"claims": len(two), "supported": sum(vs[1] == "supported" for vs in two)} if (two := [vs for vs in claude.values() if len(vs) >= 2]) else None
        out["claude"] = {"claims": len(claude), "verdicts": len(allv), **{k: allv.count(k) for k in V}, "supported_share": round(allv.count("supported") / len(allv), 3),
                         "raters_identical": sum(vs[0] == vs[1] for vs in two), "claims_with_two_raters": len(two),
                         "both_supported": sum(vs[0] == vs[1] == "supported" for vs in two)}
    if codex:
        cv = list(codex.values())
        out["codex"] = {"claims": len(codex), **{k: cv.count(k) for k in V}, "supported_share": round(cv.count("supported") / len(cv), 3)}
    both = [k for k in claude if k in codex]
    if both:
        pairs = [(v == "supported", codex[k] == "supported") for k in both for v in claude[k]]
        out["cross"] = {"claims": len(both), "pairs": len(pairs), "identical": sum(v == codex[k] for k in both for v in claude[k]),
                        "binary_agreement": round(sum(a == b for a, b in pairs) / len(pairs), 3), "kappa": round(kappa_binary(pairs), 2),
                        "claude_supported": round(sum(a for a, _ in pairs) / len(pairs), 3), "codex_supported": round(sum(b for _, b in pairs) / len(pairs), 3)}
    out["distinct_claims_audited"] = len(set(claude) | set(codex))
    return out


def main() -> None:
    s = audit_stats()
    print(json.dumps(s, indent=1))


if __name__ == "__main__":
    main()
