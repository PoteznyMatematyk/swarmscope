import json
from pathlib import Path
import re
import sys

# items for cashiers masters
ITEMS = [
    (1, "Education", ["5,432", "5432"]),
    (2, "Business", ["5,269", "5269"]),
    (3, "Social Sciences", ["2,749", "2749"]),
    (4, "Visual & Performing Arts", ["2,134", "2134"]),
    (4, "Visual", ["2,134", "2134"]),
    (5, "Psychology", ["1,544", "1544"]),
]

batch_name = "datausa-cashiers-masters_004"
bpath = Path(f"work/batches/datausa-cashiers-masters/{batch_name}.jsonl")
records = [json.loads(line) for line in bpath.read_text(encoding="utf-8").splitlines() if line.strip()]

print(f"Loaded {len(records)} records")
