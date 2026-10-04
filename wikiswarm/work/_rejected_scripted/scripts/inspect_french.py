import json
from pathlib import Path
import re

fam = "datausa-language-french"
bdir = Path(f"work/batches/{fam}")
files = sorted(bdir.glob("*.jsonl"))

for f in files:
    recs = [json.loads(line) for line in f.read_text(encoding="utf-8").splitlines() if line.strip()]
    print(f"File {f.name}: {len(recs)} records")

sample_texts = []
for f in files:
    for line in f.read_text(encoding="utf-8").splitlines():
        if line.strip():
            sample_texts.append(json.loads(line)["text"])

for i in range(min(8, len(sample_texts))):
    print(f"=== Sample {i} ===")
    print(sample_texts[i])
