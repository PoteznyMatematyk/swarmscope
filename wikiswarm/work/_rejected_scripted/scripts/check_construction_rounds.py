import json
from pathlib import Path
import re

fam = "datausa-construction-workforce"
bdir = Path(f"work/batches/{fam}")
files = sorted(bdir.glob("*.jsonl"))

rounds_map = {}
for f in files:
    for line in f.read_text(encoding="utf-8").splitlines():
        if not line.strip(): continue
        rec = json.loads(line)
        txt = rec["text"]
        # find patterns like R1 <state>, R2 <state>, etc.
        m = re.findall(r'\b(R[1-6]|round\s*[1-6])\b[^.;\n]+', txt, re.IGNORECASE)
        for match in m:
            pass

# Let's check states appearing near R1-R6
for f in files:
    for line in f.read_text(encoding="utf-8").splitlines():
        if not line.strip(): continue
        rec = json.loads(line)
        txt = rec["text"]
        for r_num in range(1, 7):
            m = re.findall(rf'\bR{r_num}\b[^.;\n]+', txt, re.IGNORECASE)
            for match in m:
                # check which state is in match
                for st in ["New York", "California", "Texas", "Florida", "Illinois", "Pennsylvania", "Ohio", "Georgia", "North Carolina", "Michigan"]:
                    if st.lower() in match.lower():
                        rounds_map.setdefault(r_num, set()).add(st)

print("Construction rounds states found:")
for r_num in sorted(rounds_map):
    print(f"R{r_num}: {rounds_map[r_num]}")
