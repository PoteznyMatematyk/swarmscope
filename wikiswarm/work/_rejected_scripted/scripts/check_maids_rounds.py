import json
from pathlib import Path
import re

bdir = Path("work/batches/datausa-maids-wage")
for f in sorted(bdir.glob("*.jsonl")):
    for line in f.read_text(encoding="utf-8").splitlines():
        if not line.strip(): continue
        rec = json.loads(line)
        txt = rec["text"]
        for r_num in range(1, 7):
            matches = re.findall(rf'\b(?:R{r_num}|round\s*{r_num}|prompt\s*#{r_num})\b[^.;\n]+', txt, re.IGNORECASE)
            for m in matches:
                print(f"[{f.name}] R{r_num}: {m}")
        # check transitions
        tr = re.findall(r'(?:female|male)\s*\d{4}\s*->\s*(?:female|male)\s*\d{4}', txt, re.IGNORECASE)
        if tr:
            print(f"[{f.name}] TRANS: {tr}")
