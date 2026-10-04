import json
from pathlib import Path
import re

bdir = Path("work/batches/datausa-poverty-county")
for f in sorted(bdir.glob("*.jsonl")):
    for line in f.read_text(encoding="utf-8").splitlines():
        if not line.strip(): continue
        rec = json.loads(line)
        txt = rec["text"]
        for r_num in range(1, 7):
            matches = re.findall(rf'\b(?:R{r_num}|round\s*{r_num})\b[^.;\n]+', txt, re.IGNORECASE)
            for m in matches:
                if any(w in m.lower() for w in ["county", "flathead", "merced", "san juan", "saginaw", "r5", "r6"]):
                    print(f"[{f.name}] R{r_num}: {m}")
