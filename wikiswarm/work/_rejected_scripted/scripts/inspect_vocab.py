import json
from pathlib import Path
import re

families = [
    'datausa-cashiers-masters',
    'datausa-sector61-state',
    'datausa-construction-workforce',
    'datausa-clothing-workforce',
    'datausa-language-french',
    'datausa-cashiers-bachelors',
    'datausa-poverty-county',
    'datausa-maids-wage'
]

for fam in families:
    bdir = Path(f'work/batches/{fam}')
    files = list(bdir.glob('*.jsonl'))
    print(f'=== Family: {fam} ({len(files)} files) ===')
    items = set()
    values = set()
    kinds = set()
    sample_texts = []
    for f in files:
        for line in f.read_text(encoding='utf-8').splitlines():
            if not line.strip(): continue
            rec = json.loads(line)
            sample_texts.append(rec['text'])
            if len(sample_texts) <= 5:
                pass
    print(f'Total records in {fam}: {len(sample_texts)}')
    # Let's print the first 3 posts
    for i, t in enumerate(sample_texts[:3]):
        print(f'--- Post {i} ---')
        print(t[:250].replace('\n', ' '))
