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

diff_keys = []
for k in set(ref_out) | set(my_out):
    if ref_out.get(k) != my_out.get(k):
        diff_keys.append(k)

print(f"Diff keys: {diff_keys}")
for k in sorted(diff_keys):
    print(f"\n=== Key: {k} ===")
    print("Ref:", repr(ref_out.get(k))[:300])
    print("Got:", repr(my_out.get(k))[:300])
