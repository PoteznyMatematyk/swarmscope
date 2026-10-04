import json
from pathlib import Path
import re

fam = "datausa-clothing-workforce"
bdir = Path(f"work/batches/{fam}")
files = sorted(bdir.glob("*.jsonl"))

rounds_states = {}
for f in files:
    for line in f.read_text(encoding="utf-8").splitlines():
        if not line.strip(): continue
        rec = json.loads(line)
        txt = rec["text"]
        for r_num in range(1, 7):
            matches = re.findall(rf'\b(?:R{r_num}|round\s*{r_num}|state\s*#{r_num})\b[^.;\n]+', txt, re.IGNORECASE)
            for m in matches:
                for st in ["California", "New York", "Texas", "Florida", "Illinois", "Pennsylvania", "Ohio", "Georgia", "North Carolina", "Michigan", "Washington", "New Jersey"]:
                    if st.lower() in m.lower():
                        rounds_states.setdefault(r_num, set()).add(st)

print("Clothing rounds states found:")
for r_num in sorted(rounds_states):
    print(f"R{r_num}: {rounds_states[r_num]}")
