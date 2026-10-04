import json
from pathlib import Path
import re

for b_idx in range(4, 9):
    b_path = Path(f"work/batches/datausa-cashiers-masters/datausa-cashiers-masters_{b_idx:03d}.jsonl")
    records = [json.loads(line) for line in b_path.read_text(encoding="utf-8").splitlines() if line.strip()]
    print(f"=== Batch {b_idx} ({len(records)} records) ===")
    for i, r in enumerate(records):
        txt = r["text"]
        # find sentences mentioning any degree / round
        sents = re.split(r'(?<=[.;!?\n])\s+', txt)
        matches = [s for s in sents if any(k in s.lower() for k in ['education', 'business', 'social sciences', 'visual', 'psychology', 'r1', 'r2', 'r3', 'r4', 'r5'])]
        if not matches:
            print(f"  Rec {i} [{r['record_id'][:8]}]: NO MATCH: {txt[:80]}")
