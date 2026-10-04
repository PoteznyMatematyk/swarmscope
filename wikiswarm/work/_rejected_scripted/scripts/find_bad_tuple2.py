import json
from pathlib import Path
import sys
sys.path.insert(0, str(Path('gate').resolve()))
from run_gate import check_tuple
from common import load_families, read_jsonl

fams = load_families()['families']
bdir = Path('work/batches')
edir = Path('work/extract')
batches = sorted(bdir.rglob("*.jsonl"))
for b in batches:
    rel = b.relative_to(bdir).with_suffix(".json")
    ef = edir / rel
    if not ef.exists():
        continue
    rows = {r['record_id']: r for r in read_jsonl(b)}
    d = json.loads(ef.read_text(encoding='utf-8'))
    for r in d['records']:
        for i, t in enumerate(r.get('tuples', [])):
            why = check_tuple(t, rows[r['record_id']]['text'], fams)
            if why:
                print(f"{ef}: record {r['record_id']} tuple {i}: {why} -> {t}")
