import json
from pathlib import Path
import re

fam = "datausa-sector61-state"
bdir = Path(f"work/batches/{fam}")
files = sorted(bdir.glob("*.jsonl"))

states_found = set()
for f in files:
    recs = [json.loads(line) for line in f.read_text(encoding="utf-8").splitlines() if line.strip()]
    print(f"File {f.name}: {len(recs)} records")
    for r in recs:
        # find mentions of states or sequences like ->
        matches = re.findall(r'([A-Z][a-z]+(?:\s+[A-Z][a-z]+)?)\s*->\s*([A-Z][a-z]+(?:\s+[A-Z][a-z]+)?)', r["text"])
        for m in matches:
            states_found.update(m)
        r_matches = re.findall(r'\b(R[1-9]|STATE\d?)\b', r["text"])

print(f"States mentioned in transitions: {sorted(states_found)}")

# print first 5 records of 001
for r in [json.loads(line) for line in files[0].read_text(encoding="utf-8").splitlines()[:5]]:
    print("---")
    print(r["text"][:300])
