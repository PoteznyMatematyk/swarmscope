"""Write deterministic tracer leads (trace.txt / trace.json) for every episode of data/work/windows/manifest.json.

    python scripts/make_trace_leads.py [EPISODE ...]      # default: all episodes with chat windows (E5 is skipped)

The leads are units (urls, files, identifiers) that spread between agents inside the episode window, ranked by adopters.
They are hints for the synthesizer (question Q3), not claims: adoption by mention does not tell request from use.
"""

import json
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
WORK = ROOT / "data" / "work"
PY = ROOT / "swarmscope" / ".venv" / ("Scripts/python.exe" if os.name == "nt" else "bin/python")
manifest = json.loads((WORK / "windows" / "manifest.json").read_text(encoding="utf-8"))
wanted = sys.argv[1:] or [n for n, ep in manifest.items() if "OUTREACH_APPROVAL_REQUEST" not in ep["subtypes"]]

for name in wanted:
    ep = manifest[name]
    out = WORK / "runs" / "full" / name
    out.mkdir(parents=True, exist_ok=True)
    done = subprocess.run(
        [str(PY), str(WORK / "tool" / "run.py"), "trace", "--source", "ai_village", "--subtypes", "AGENT_TALK,USER_TALK",
         "--start", ep["start"], "--end", ep["end"], "--min-adopters", "3", "--top", "40", "--out", str(out / "trace.json")],
        capture_output=True, text=True, encoding="utf-8", env={**os.environ, "PYTHONUTF8": "1"})
    out.mkdir(parents=True, exist_ok=True)   # the external drive once dropped a directory mid-run
    (out / "trace.txt").write_text(done.stdout, encoding="utf-8")
    print(f"{name}: {max(len(done.stdout.splitlines()) - 1, 0)} cascades" + (f"  ERROR {done.stderr[-300:]}" if done.returncode else ""))
