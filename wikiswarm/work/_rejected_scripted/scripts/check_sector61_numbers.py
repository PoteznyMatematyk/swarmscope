import json
from pathlib import Path
import re

fam = "datausa-sector61-state"
bdir = Path(f"work/batches/{fam}")
files = sorted(bdir.glob("*.jsonl"))

for f in files:
    for line in f.read_text(encoding="utf-8").splitlines():
        if not line.strip(): continue
        rec = json.loads(line)
        txt = rec["text"]
        # search for numbers >= 1000
        nums = re.findall(r'\b\d{1,3}(?:,\d{3})+\b|\b\d{4,9}\b', txt)
        # ignore dates/years
        real_nums = [n for n in nums if not (n.startswith("201") or n.startswith("202") or n.startswith("19"))]
        if real_nums:
            print(f"[{f.name}] Rec {rec['record_id'][:8]}: {real_nums} in: {txt[:120]}")
