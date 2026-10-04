import json
from pathlib import Path
import re
import sys
sys.path.insert(0, str(Path("gate").resolve()))
from common import US_STATES

bdir = Path("work/batches/datausa-clothing-workforce")
all_states = set()
for f in sorted(bdir.glob("*.jsonl")):
    for line in f.read_text(encoding="utf-8").splitlines():
        if not line.strip(): continue
        rec = json.loads(line)
        txt = rec["text"]
        for st_name in US_STATES:
            if re.search(rf'\b{re.escape(st_name)}\b', txt, re.IGNORECASE):
                all_states.add(st_name.title())

print("All states in clothing workforce:", sorted(all_states))
