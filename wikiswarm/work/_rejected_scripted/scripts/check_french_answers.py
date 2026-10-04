import json
from pathlib import Path
import re

bdir = Path("work/batches/datausa-language-french")
for f in sorted(bdir.glob("*.jsonl")):
    for line in f.read_text(encoding="utf-8").splitlines():
        if not line.strip(): continue
        rec = json.loads(line)
        txt = rec["text"]
        if any(w in txt.lower() for w in ["answer", "confirmed", "correct", "%"]):
            m = re.findall(r'\b(?:R[1-6]|round\s*[1-6])\b[^.;\n]+', txt, re.IGNORECASE)
            if m:
                print(f"[{f.name}] Rec {rec['record_id'][:8]}: {m}")
