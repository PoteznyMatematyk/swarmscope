"""Acceptance gate for wikiswarm. gate/HASHES.json pins every file in gate/; any edit is a REJECT.

    python gate/run_gate.py s1                 # posts table + batches
    python gate/run_gate.py s2 [--partial]     # extraction files -> work/tuples_verified.jsonl
    python gate/run_gate.py s3                 # pipeline aggregator vs reference + gold units
    python gate/run_gate.py all
    python gate/run_gate.py --baseline         # re-hash gate/ after an intended change

Exit code 0 = ACCEPT, 1 = REJECT. The last line printed is always 'GATE <stage> ACCEPT|REJECT'.
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import subprocess
import sys
import tempfile
from collections import Counter, defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from common import (CACHE_RE, GATE, KINDS, NO_TUPLE_REASONS, ROOT, WORK, item_in_quote, load_families,  # noqa: E402
                    read_jsonl, signature_after, write_json, ws)
from ref_aggregate import aggregate  # noqa: E402
from ref_prep import build_posts  # noqa: E402

MAX_RECORDS, MAX_CHARS = 30, 15000
TUPLE_FIELDS = {"family", "round", "item", "value", "kind", "used_cache", "task_clock", "cohort_tier",
                "corrects_value", "quote"}


# ---------------------------------------------------------------- tripwire
def _gate_files():
    return sorted(p for p in GATE.rglob("*") if p.is_file() and p.name != "HASHES.json"
                  and "__pycache__" not in p.parts)


def _hashes():
    return {p.relative_to(GATE).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest() for p in _gate_files()}


def tripwire() -> list[str]:
    hf = GATE / "HASHES.json"
    if not hf.exists():
        return ["gate/HASHES.json missing"]
    want, have = json.loads(hf.read_text(encoding="utf-8")), _hashes()
    return [f"gate file changed or added/removed: {k}" for k in sorted(set(want) | set(have))
            if want.get(k) != have.get(k)]


# ---------------------------------------------------------------- S1
def candidate_records(posts):
    recs = {}
    for p in posts:  # posts are sorted by (wall_time, post_id) -> first seen = earliest candidate origin
        if p["candidate"] and p["record_id"] not in recs:
            recs[p["record_id"]] = {"record_id": p["record_id"], "text": p["text"],
                                    "page_family": p["page_family"], "wall_time": p["wall_time"]}
    return recs


def check_s1() -> list[str]:
    errs = []
    pf = WORK / "posts.jsonl"
    if not pf.exists():
        return ["work/posts.jsonl missing"]
    ref = build_posts()
    got = list(read_jsonl(pf))
    if len(got) != len(ref):
        errs.append(f"posts.jsonl has {len(got)} rows, expected {len(ref)}")
    for i, (g, r) in enumerate(zip(got, ref)):
        if g != r:
            diff = sorted(k for k in set(g) | set(r) if g.get(k) != r.get(k))
            errs.append(f"posts.jsonl row {i} differs from spec in fields {diff} (post_id {r['post_id']})")
            if len(errs) > 8:
                break
    recs = candidate_records(ref)
    seen = Counter()
    bdir = WORK / "batches"
    files = sorted(bdir.rglob("*.jsonl")) if bdir.exists() else []
    if not files:
        errs.append("no batch files under work/batches/")
    for f in files:
        rel = f.relative_to(bdir).as_posix()
        rows = list(read_jsonl(f))
        fam = f.parent.name
        if not re.fullmatch(rf"{re.escape(fam)}_\d{{3}}\.jsonl", f.name):
            errs.append(f"{rel}: name must be <family>_NNN.jsonl inside folder <family>/")
        chars = sum(len(r.get("text", "")) for r in rows)
        if len(rows) > MAX_RECORDS or (chars > MAX_CHARS and len(rows) > 1):
            errs.append(f"{rel}: {len(rows)} records / {chars} chars exceeds batch limits")
        for r in rows:
            seen[r.get("record_id")] += 1
            want = recs.get(r.get("record_id"))
            if want is None:
                errs.append(f"{rel}: record {r.get('record_id')} is not a candidate record")
            elif r != want:
                errs.append(f"{rel}: record {r['record_id']} fields differ from spec")
            elif want["page_family"] != fam:
                errs.append(f"{rel}: record {r['record_id']} has page_family {want['page_family']} != folder {fam}")
    missing = set(recs) - set(seen)
    dup = [k for k, c in seen.items() if c > 1]
    if missing:
        errs.append(f"{len(missing)} candidate records are in no batch")
    if dup:
        errs.append(f"{len(dup)} records appear in more than one batch")
    print(f"S1: posts {len(got)}/{len(ref)}, candidate records {len(recs)}, batch files {len(files)}")
    return errs[:40]


# ---------------------------------------------------------------- S2
def _in_quote(v: str, quote: str) -> bool:
    strip = lambda s: re.sub(r"[,\s]", "", s)  # noqa: E731
    return bool(strip(v)) and strip(v) in strip(quote)


NUM_TOKEN = re.compile(r"\d[\d,]*(?:\.\d+)?")


def _value_ok(v: str, quote: str) -> bool:
    """Every number in the value must be a whole number token of the quote that is not part of a clock
    time (blocks '12' taken from '12.4%' and '10' taken from '10:25:54')."""
    nums = NUM_TOKEN.findall(v)
    if not nums:  # textual values such as 'NA' must appear as a whole word
        return bool(v.strip()) and re.search(rf"(?<!\w){re.escape(v.strip())}(?!\w)", quote) is not None
    toks = {m.group(0).replace(",", "") for m in NUM_TOKEN.finditer(quote)
            if not re.match(r":\d", quote[m.end():m.end() + 2]) and not (m.start() > 0 and quote[m.start() - 1] == ":")}
    return all(n.replace(",", "") in toks for n in nums)


def check_tuple(t: dict, text: str, fams: dict) -> str | None:
    if set(t) != TUPLE_FIELDS:
        return "fields"
    if t["kind"] not in KINDS:
        return "kind"
    if t["family"] not in fams:
        return "family"
    if t["round"] is not None and not (isinstance(t["round"], int) and 1 <= t["round"] <= 12):
        return "round"
    q = t["quote"]
    if not isinstance(q, str) or len(q) < 8 or len(q) > 400:
        return "quote_length"
    if ws(q) not in ws(text):
        return "quote_not_verbatim"
    if not isinstance(t["item"], str) or not item_in_quote(t["item"], q):
        return "item_not_in_quote"
    if t["value"] is not None and not (isinstance(t["value"], str) and _in_quote(t["value"], q)):
        return "value_not_in_quote"
    if t["value"] is not None and not _value_ok(t["value"], q):
        return "value_not_whole_number_in_quote"
    for k in ("task_clock", "cohort_tier"):
        if t[k] is not None and not (isinstance(t[k], str) and ws(t[k]) in ws(q)):
            return f"{k}_not_in_quote"
    if not isinstance(t["used_cache"], bool):
        return "used_cache_type"
    if t["used_cache"] and not CACHE_RE.search(q):
        return "used_cache_unsupported"
    if t["corrects_value"] is not None:
        if t["kind"] != "correction" or not (isinstance(t["corrects_value"], str) and _in_quote(t["corrects_value"], q)):
            return "corrects_value"
    return None


def check_s2(partial: bool) -> list[str]:
    errs = []
    fams = load_families()["families"]
    kw = {f: re.compile(v["keywords"], re.IGNORECASE) for f, v in fams.items()}
    bdir, edir = WORK / "batches", WORK / "extract"
    batches = sorted(bdir.rglob("*.jsonl")) if bdir.exists() else []
    if not batches:
        return ["no batches; run S1 first"]
    verified, reasons = [], Counter()
    n_files = n_records = n_tuples = n_no_tuple = fam_unsupported = 0
    missing_files = []
    for b in batches:
        rel = b.relative_to(bdir).with_suffix(".json")
        ef = edir / rel
        if not ef.exists():
            missing_files.append(rel.as_posix())
            continue
        n_files += 1
        rows = {r["record_id"]: r for r in read_jsonl(b)}
        try:
            out = json.loads(ef.read_text(encoding="utf-8"))
        except Exception as e:  # noqa: BLE001
            errs.append(f"extract/{rel.as_posix()}: invalid JSON ({e})")
            continue
        if out.get("batch") != b.relative_to(bdir).as_posix():
            errs.append(f"extract/{rel.as_posix()}: 'batch' must be {b.relative_to(bdir).as_posix()!r}")
        recs = out.get("records") or []
        ids = [r.get("record_id") for r in recs]
        if sorted(ids) != sorted(rows) or len(set(ids)) != len(ids):
            errs.append(f"extract/{rel.as_posix()}: records must cover every batch record exactly once")
            continue
        for r in recs:
            n_records += 1
            text = rows[r["record_id"]]["text"]
            ts = r.get("tuples")
            if not isinstance(ts, list):
                errs.append(f"extract/{rel.as_posix()}: record {r['record_id']} has no tuples list")
                continue
            if not ts:
                n_no_tuple += 1
                if r.get("no_tuple_reason") not in NO_TUPLE_REASONS:
                    errs.append(f"extract/{rel.as_posix()}: record {r['record_id']} empty tuples needs no_tuple_reason")
                continue
            if r.get("no_tuple_reason") is not None:
                errs.append(f"extract/{rel.as_posix()}: record {r['record_id']} has tuples and a no_tuple_reason")
            for t in ts:
                n_tuples += 1
                why = check_tuple(t, text, fams) if isinstance(t, dict) else "not_object"
                if why:
                    reasons[why] += 1
                    continue
                if t["family"] != rows[r["record_id"]]["page_family"] and not kw[t["family"]].search(text):
                    fam_unsupported += 1
                verified.append({**t, "record_id": r["record_id"], "wall_time": rows[r["record_id"]]["wall_time"],
                                 "page_family": rows[r["record_id"]]["page_family"],
                                 "signature": signature_after(text, t["quote"]),
                                 "batch": b.relative_to(bdir).as_posix()})
    verified.sort(key=lambda t: (t["wall_time"], t["record_id"], t["quote"], t["item"]))
    with open(WORK / "tuples_verified.jsonl", "w", encoding="utf-8") as f:
        for t in verified:
            f.write(json.dumps(t, ensure_ascii=False) + "\n")
    rejected = sum(reasons.values())
    rep = {"batch_files": len(batches), "extract_files": n_files, "missing_extract_files": len(missing_files),
           "records": n_records, "records_without_tuples": n_no_tuple, "tuples": n_tuples,
           "tuples_accepted": len(verified), "tuples_rejected": rejected, "rejected_by_reason": dict(reasons),
           "family_keyword_unsupported": fam_unsupported,
           "kinds": dict(Counter(t["kind"] for t in verified)),
           "families": dict(Counter(t["family"] for t in verified))}
    write_json(WORK / "gate_s2_report.json", rep)
    print("S2:", json.dumps(rep, sort_keys=True))
    if missing_files and not partial:
        errs.append(f"{len(missing_files)} batches have no extract file, e.g. {missing_files[:3]}")
    if n_tuples and rejected / n_tuples > 0.05:
        errs.append(f"tuple rejection rate {rejected / n_tuples:.1%} > 5% ({dict(reasons)})")
    if verified and fam_unsupported / len(verified) > 0.10:
        errs.append(f"family label unsupported by post text for {fam_unsupported / len(verified):.1%} of tuples (> 10%)")
    if n_records and n_no_tuple / n_records > 0.85:
        errs.append(f"{n_no_tuple}/{n_records} records without tuples: suspiciously lazy extraction")
    return errs[:40]


# ---------------------------------------------------------------- S3
def _norm(o):
    if isinstance(o, float):
        return round(o, 3)
    if isinstance(o, dict):
        return {k: _norm(v) for k, v in o.items()}
    if isinstance(o, list):
        return sorted((_norm(x) for x in o), key=lambda x: json.dumps(x, sort_keys=True))
    return o


def _run_pipeline(tuples_path: Path, out: Path) -> str | None:
    env = dict(os.environ, PYTHONPATH=str(ROOT / "src"))
    p = subprocess.run([sys.executable, "-m", "wikiswarm.aggregate", "--tuples", str(tuples_path), "--out", str(out)],
                       cwd=ROOT, env=env, capture_output=True, text=True, timeout=600)
    if p.returncode != 0:
        return f"wikiswarm.aggregate failed: {p.stderr[-800:]}"
    return None


def _compare(name, got, want) -> list[str]:
    g, w = _norm(got), _norm(want)
    if g == w:
        return []
    keys = sorted(k for k in set(g) | set(w) if g.get(k) != w.get(k))
    return [f"{name}: pipeline metrics differ from reference in keys {keys}"]


def check_s3() -> list[str]:
    errs = []
    fx = GATE / "fixtures" / "synthetic_tuples.jsonl"
    with tempfile.TemporaryDirectory() as td:
        out = Path(td) / "m.json"
        e = _run_pipeline(fx, out)
        if e:
            return [e]
        errs += _compare("synthetic fixture", json.loads(out.read_text(encoding="utf-8")),
                         json.loads((GATE / "fixtures" / "expected_metrics.json").read_text(encoding="utf-8")))
    tv = WORK / "tuples_verified.jsonl"
    if not tv.exists():
        return errs + ["work/tuples_verified.jsonl missing (run gate s2)"]
    mf = WORK / "metrics.json"
    e = _run_pipeline(tv, mf)
    if e:
        return errs + [e]
    ref = aggregate(list(read_jsonl(tv)))
    errs += _compare("real data", json.loads(mf.read_text(encoding="utf-8")), ref)
    gold = json.loads((GATE / "fixtures" / "gold_units.json").read_text(encoding="utf-8"))
    units = {(u["family"], u["round"], u["item"]): u for u in ref["units"]}
    preds = {(p["family"], p["round"], p["item"]): p for p in ref["wrong_predictions"]}
    found, soft = [], []
    for g in gold["units"]:
        u = units.get((g["family"], g["round"], g["item"]))
        ok = u is not None and (g["value"] is None or u["consensus_value"] == g["value"])
        found.append({**g, "found": u is not None, "value_ok": ok,
                      "got_value": u["consensus_value"] if u else None})
        if g["required"] and u is None:
            errs.append(f"gold unit missing: {g['family']} R{g['round']} {g['item']}")
        elif g["value"] is not None and not ok:
            soft.append(f"gold unit {g['family']} R{g['round']} {g['item']}: consensus {u['consensus_value'] if u else None} != {g['value']}")
    for g in gold["wrong_predictions"]:
        found.append({**g, "found": (g["family"], g["round"], g["item"]) in preds})
    write_json(WORK / "gate_s3_report.json", {"gold": found, "soft_warnings": soft,
                                              "headline": {k: ref[k] for k in ref if k not in ("units", "wrong_values", "wrong_predictions", "revealers")}})
    print("S3: gold", sum(1 for f in found if f.get("found")), "/", len(found), "found; soft warnings:", soft)
    return errs[:40]


# ---------------------------------------------------------------- main
def main() -> int:
    args = sys.argv[1:]
    if args == ["--baseline"]:
        write_json(GATE / "HASHES.json", _hashes())
        print("baseline written")
        return 0
    stage = args[0] if args else "all"
    errs = tripwire()
    if not errs:
        if stage in ("s1", "all"):
            errs += check_s1()
        if stage in ("s2", "all") and not errs:
            errs += check_s2("--partial" in args)
        if stage in ("s3", "all") and not errs:
            errs += check_s3()
    for e in errs:
        print("ERROR:", e)
    print(f"GATE {stage} {'REJECT' if errs else 'ACCEPT'}")
    return 1 if errs else 0


if __name__ == "__main__":
    sys.exit(main())
