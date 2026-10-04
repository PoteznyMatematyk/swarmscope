import json, re
from pathlib import Path

bdir = Path('work/batches/datausa-clothing-workforce')
for f in sorted(bdir.glob('*.jsonl')):
    for line in f.read_text(encoding='utf-8').splitlines():
        if not line.strip(): continue
        rec = json.loads(line)
        txt = rec['text']
        m = re.findall(r'\b\d{2,3},\d{3}\b', txt)
        if m:
            print(f'[{rec["record_id"][:8]}] {m} in: {txt[:120]}')
