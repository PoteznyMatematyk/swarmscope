"""Operator sweep: independently re-run the acceptance gate on every packet OUT folder of a runs subfolder (the binding check).

    python scripts/accept_all.py flash            # data/work/runs/flash/*
    python scripts/accept_all.py claude bench_haiku bench_opus bench_fable

Prints one row per folder and a per-runs-dir summary (first-pass quote reject rate and claims per accepted chunk), and
writes data/work/runs/<dir>/ACCEPT_SWEEP.json. Exit code 0 only when every folder is ACCEPT.
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
WORK = ROOT / "data" / "work"
GATE = Path(__file__).resolve().parent / "accept_packet.py"


def chunk_path(name: str) -> Path | None:
    ep, _, c = name.rpartition("_c")
    return WORK / "windows" / ep / f"chunk_{c}.txt" if ep and c.isdigit() else None


def main() -> int:
    dirs = sys.argv[1:] or ["flash", "claude"]
    worst = 0
    for d in dirs:
        base = WORK / "runs" / d
        rows = []
        for out in sorted(p for p in base.glob("*_c*") if p.is_dir()):
            chunk = chunk_path(out.name)
            if not chunk or not chunk.exists():
                continue
            r = subprocess.run([sys.executable, str(GATE), str(out), "--chunk", str(chunk)], capture_output=True, text=True, encoding="utf-8")
            try:
                j = json.loads(r.stdout)
            except Exception:  # noqa: BLE001
                j = {"verdict": "CRASH", "fails": [r.stderr[-200:]], "stats": {}, "warns": []}
            lens_stats = {k: v for k, v in j.get("stats", {}).items() if isinstance(v, dict)}
            rej = [s["quote_reject_rate_v1"] for s in lens_stats.values() if s.get("quote_reject_rate_v1") is not None]
            row = {"chunk": out.name, "verdict": j["verdict"], "claims_v2": sum(s.get("claims_v2", 0) for s in lens_stats.values()),
                   "quote_reject_rate_v1": round(sum(rej) / len(rej), 4) if rej else None, "fails": j.get("fails", [])[:5], "warns": len(j.get("warns", []))}
            rows.append(row)
            worst = max(worst, {"ACCEPT": 0, "REVISE": 1, "REJECT": 2}.get(j["verdict"], 3))
            print(f"{d:<12}{out.name:<24}{j['verdict']:<8} claims={row['claims_v2']:<4} reject_v1={row['quote_reject_rate_v1']}  " + (row["fails"][0][:110] if row["fails"] else ""))
        acc = [r for r in rows if r["verdict"] == "ACCEPT"]
        rates = [r["quote_reject_rate_v1"] for r in acc if r["quote_reject_rate_v1"] is not None]
        summary = {"runs_dir": d, "folders": len(rows), "accepted": len(acc), "claims_in_accepted": sum(r["claims_v2"] for r in acc),
                   "mean_quote_reject_rate_v1": round(sum(rates) / len(rates), 4) if rates else None, "rows": rows}
        (base / "ACCEPT_SWEEP.json").write_text(json.dumps(summary, indent=1), encoding="utf-8") if base.exists() else None
        print(f"== {d}: {summary['accepted']}/{summary['folders']} ACCEPT, {summary['claims_in_accepted']} claims, mean first-pass quote reject rate {summary['mean_quote_reject_rate_v1']}")
    return worst


if __name__ == "__main__":
    sys.exit(main())
