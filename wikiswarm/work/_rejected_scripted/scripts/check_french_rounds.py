import json
from pathlib import Path
import re
import sys

sys.path.insert(0, str(Path("gate").resolve()))
from common import US_STATES

bdir = Path("work/batches/datausa-language-french")
all_states = set()
rounds_states = {}
for f in sorted(bdir.glob("*.jsonl")):
    for line in f.read_text(encoding="utf-8").splitlines():
        if not line.strip(): continue
        rec = json.loads(line)
        txt = rec["text"]
        for st_name, code in US_STATES.items():
            if re.search(rf'\b{re.escape(st_name)}\b', txt, re.IGNORECASE) or re.search(rf'\b{code}\b', txt):
                all_states.add((st_name.title(), code))
        for r_num in range(1, 7):
            matches = re.findall(rf'\b(?:R{r_num}|round\s*{r_num})\b[^.;\n]+', txt, re.IGNORECASE)
            for m in matches:
                for st_name, code in US_STATES.items():
                    if st_name.lower() in m.lower() or re.search(rf'\b{code}\b', m):
                        rounds_states.setdefault(r_num, set()).add(code)

print("All states in french:", sorted(all_states))
print("Rounds states in french:")
for r in sorted(rounds_states):
    print(f"R{r}: {sorted(rounds_states[r])}")
