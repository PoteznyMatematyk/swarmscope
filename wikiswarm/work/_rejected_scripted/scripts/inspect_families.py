import json
from pathlib import Path

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
    p = Path(f'work/batches/{fam}/{fam}_001.jsonl')
    if p.exists():
        lines = [json.loads(l) for l in p.read_text(encoding='utf-8').strip().split('\n')[:4]]
        print(f'=== {fam} ===')
        for l in lines:
            print(' ', l.get('round'), repr(l.get('text'))[:120])
