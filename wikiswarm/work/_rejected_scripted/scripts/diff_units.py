import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path("gate").resolve()))
from ref_aggregate import aggregate as ref_agg
from common import read_jsonl

sys.path.insert(0, str(Path("src").resolve()))
from wikiswarm.aggregate import aggregate as my_agg

tv = list(read_jsonl(Path("work/tuples_verified.jsonl")))
ref_out = ref_agg(tv)
my_out = my_agg(tv)

ref_u = {(u["family"], u["round"], u["item"]): u for u in ref_out["units"]}
my_u = {(u["family"], u["round"], u["item"]): u for u in my_out["units"]}

print("Missing in my_u:", set(ref_u) - set(my_u))
print("Extra in my_u:", set(my_u) - set(ref_u))

for k in sorted(ref_u):
    ru, mu = ref_u[k], my_u[k]
    diff = {field: (ru[field], mu[field]) for field in ru if ru[field] != mu[field]}
    if diff:
        print(f"Diff in {k}: {diff}")
        break
