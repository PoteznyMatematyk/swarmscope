"""Per-file extraction check (read-only, safe to run in parallel).

    python gate/check_extract.py work/extract/<family>/<family>_NNN.json [more files...]

Prints every rejected tuple with its reason, then 'FILE OK' or 'FILE REJECT' per file.
Exit code 0 only if every file is OK (structure valid and no rejected tuples).
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from common import NO_TUPLE_REASONS, WORK, load_families, read_jsonl  # noqa: E402
from run_gate import check_tuple, tripwire  # noqa: E402


def check_file(path: Path, fams: dict) -> bool:
    ok = True
    try:
        rel = path.resolve().relative_to((WORK / "extract").resolve()).with_suffix(".jsonl")
    except ValueError:
        print(f"{path}: not under work/extract/")
        return False
    batch = WORK / "batches" / rel
    if not batch.exists():
        print(f"{path}: no matching batch {batch}")
        return False
    rows = {r["record_id"]: r for r in read_jsonl(batch)}
    try:
        out = json.loads(path.read_text(encoding="utf-8"))
    except Exception as e:  # noqa: BLE001
        print(f"{path}: invalid JSON: {e}")
        return False
    if out.get("batch") != rel.as_posix():
        print(f"{path}: 'batch' must be {rel.as_posix()!r}")
        ok = False
    recs = out.get("records") or []
    ids = [r.get("record_id") for r in recs]
    if sorted(ids) != sorted(rows) or len(set(ids)) != len(ids):
        missing = sorted(set(rows) - set(ids))
        extra = sorted(set(ids) - set(rows))
        print(f"{path}: records must cover the batch exactly once; missing {missing[:5]} extra {extra[:5]}")
        return False
    n_t = n_bad = n_empty = 0
    for r in recs:
        ts = r.get("tuples")
        if not isinstance(ts, list):
            print(f"  record {r['record_id']}: 'tuples' must be a list")
            ok = False
            continue
        if not ts:
            n_empty += 1
            if r.get("no_tuple_reason") not in NO_TUPLE_REASONS:
                print(f"  record {r['record_id']}: empty tuples needs no_tuple_reason in {sorted(NO_TUPLE_REASONS)}")
                ok = False
        elif r.get("no_tuple_reason") is not None:
            print(f"  record {r['record_id']}: has tuples, so no_tuple_reason must be null")
            ok = False
        for i, t in enumerate(ts):
            n_t += 1
            why = check_tuple(t, rows[r["record_id"]]["text"], fams) if isinstance(t, dict) else "not_object"
            if why:
                n_bad += 1
                ok = False
                print(f"  record {r['record_id']} tuple {i}: REJECT {why}: "
                      f"{json.dumps({k: t.get(k) for k in ('item', 'value', 'kind', 'quote')}, ensure_ascii=False)[:300]}")
    print(f"{path.name}: records {len(recs)}, empty {n_empty}, tuples {n_t}, rejected {n_bad} -> "
          f"{'FILE OK' if ok else 'FILE REJECT'}")
    return ok


def main() -> int:
    tw = tripwire()
    if tw:
        for e in tw:
            print("ERROR:", e)
        return 1
    fams = load_families()["families"]
    results = [check_file(Path(a), fams) for a in sys.argv[1:]]
    return 0 if results and all(results) else 1


if __name__ == "__main__":
    sys.exit(main())
