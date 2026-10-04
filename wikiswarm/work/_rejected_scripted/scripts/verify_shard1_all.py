import json
from pathlib import Path
import subprocess

shard1_fams = [
    ("datausa-grocery-workforce", 9),
    ("datausa-cashiers-masters", 8),
    ("datausa-sector61-state", 8),
    ("datausa-construction-workforce", 7),
    ("datausa-clothing-workforce", 8),
    ("datausa-language-french", 6),
    ("datausa-cashiers-bachelors", 1),
    ("datausa-poverty-county", 5),
    ("datausa-maids-wage", 4),
]

all_files = []
for fam, count in shard1_fams:
    for i in range(1, count + 1):
        f = Path(f"work/extract/{fam}/{fam}_{i:03d}.json")
        assert f.exists(), f"Missing file: {f}"
        all_files.append(f)

print(f"Total Shard 1 files to verify: {len(all_files)}")
failed = []
total_tuples = 0
total_empty = 0

for f in all_files:
    res = subprocess.run(["python", "gate/check_extract.py", str(f)], capture_output=True, text=True)
    out = res.stdout.strip()
    if "FILE OK" not in out:
        print(f"FAILED: {f.name}")
        print(out)
        failed.append(f)
    else:
        # parse records, tuples
        # e.g. "datausa-grocery-workforce_001.json: records 30, empty 0, tuples 69, rejected 0 -> FILE OK"
        print(out)

if failed:
    print(f"FAILED FILES: {len(failed)}")
else:
    print("ALL 56 SHARD 1 FILES VERIFIED: FILE OK!")
