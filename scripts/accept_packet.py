"""Deterministic acceptance gate for a worker packet (one chunk, one or more lenses).

Workers (Flash, sub-agents) run this in their own repair loop; the operator re-runs it independently and ONLY that
second run is binding. It trusts nothing the worker reports: it recomputes citation verification, compares the
worker's `verified_*.json` with the recomputation, checks reading receipts and cheap anti-laziness signals.

    python scripts/accept_packet.py <OUT_DIR> --chunk <chunk.txt>            # verdict JSON on stdout; exit 0 = ACCEPT
    python scripts/accept_packet.py --baseline                              # (operator) hash tool/, windows/, protocol, this script
    python scripts/accept_packet.py <OUT_DIR> --chunk <chunk.txt> --calibrate   # stats only, old-pilot layout tolerated

Layouts: <OUT_DIR>/<lens>/{claims_v1,verified_v1,claims_v2,v2_changes,verified_v2}.json + <OUT_DIR>/reading_log.jsonl,
or (calibration) the five files directly in <OUT_DIR>.
Verdicts: ACCEPT | REVISE (fixable, list of failed checks) | REJECT (forged results or tripwire hit).
Thresholds are calibrated on the three Sonnet 5.5 pilots (41-47 claims/lens, median quote 9 words, p10 5 words).
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]  # SWARM_HACKATHON
WORK = ROOT / "data" / "work"
TOOL = WORK / "tool"
BASELINE = WORK / "packets" / "tripwire.json"
PROTOCOL = ROOT / "swarmscope" / "src" / "swarmscope" / "prompts" / "battery.md"
SELF = Path(__file__).resolve()

sys.path.insert(0, str(TOOL))

LENS_Q = {
    "structure": ["Q1", "Q2", "Q3", "Q7", "Q10"],
    "friction": ["Q4", "Q5", "Q6", "Q8", "Q9", "Q11"],
    "oversight": ["Q4", "Q5", "Q6", "Q7", "Q8", "Q9", "Q11"],
}
FILES = ["claims_v1.json", "verified_v1.json", "claims_v2.json", "v2_changes.json", "verified_v2.json"]
CHANGE_KINDS = {"quote_repair", "semantic_fix", "evidence_added", "claim_added", "claim_deleted"}
EVENT_LINE = re.compile(r"^\[[^\]]+\] .{0,240}?\{([0-9a-f]{10})\}: ")

# thresholds (see module docstring)
MIN_LONG_QUOTE_SHARE = 0.80  # share of quotes with >= 5 words (pilot: ~0.90)
LONG_QUOTE_WORDS = 5
MAX_DELETED_SHARE = 0.25
MAX_UNSUPPORTED_ACTOR_SHARE = 0.10
MIN_QUINTILES = 4
DUP_QUOTE_WARN = 6


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def tree_hashes() -> dict[str, str]:
    out = {}
    for p in sorted(TOOL.rglob("*")):
        if p.is_file() and "__pycache__" not in p.parts:
            out[f"tool/{p.relative_to(TOOL).as_posix()}"] = sha(p)
    for p in sorted((WORK / "windows").rglob("*")):
        if p.is_file():
            out[f"windows/{p.relative_to(WORK / 'windows').as_posix()}"] = sha(p)
    out["protocol/battery.md"] = sha(PROTOCOL)
    out["scripts/accept_packet.py"] = sha(SELF)
    snap = WORK / "snapshot.duckdb"
    out["snapshot.duckdb#size"] = str(snap.stat().st_size)
    return out


def write_baseline() -> None:
    BASELINE.parent.mkdir(parents=True, exist_ok=True)
    h = tree_hashes()
    BASELINE.write_text(json.dumps(h, indent=1), encoding="utf-8")
    print(f"tripwire baseline: {len(h)} entries -> {BASELINE}")


def load(path: Path, fails: list[str]):
    if not path.exists():
        fails.append(f"missing file: {path.name}")
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:  # noqa: BLE001
        fails.append(f"unreadable JSON {path.name}: {type(exc).__name__}")
        return None


def parse_chunk(path: Path) -> tuple[dict[str, int], int]:
    """ref -> 1-based line number, and the number of event lines."""
    refs = {}
    for i, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        m = EVENT_LINE.match(line)
        if m:
            refs[m.group(1)] = i
    return refs, len(refs)


def ref10(event_id: str) -> str:
    return event_id.rsplit(":", 1)[-1].replace("-", "")[:10]


def claim_map(verified: dict) -> dict:
    out = {}
    for batch in (verified or {}).get("batches", []):
        for c in batch.get("claims", []):
            out[c.get("id")] = (c.get("status"), [e.get("status") for e in c.get("evidence", [])])
    return out


def check_receipts(out: Path, chunk_refs: dict[str, int], n_events: int, fails: list[str], warns: list[str], stats: dict) -> None:
    p = out / "reading_log.jsonl"
    if not p.exists():
        fails.append("missing file: reading_log.jsonl (reading receipts)")
        return
    lines = sorted(chunk_refs.values())
    covered: set[int] = set()
    bad = 0
    slices = 0
    for raw in p.read_text(encoding="utf-8").splitlines():
        if not raw.strip():
            continue
        try:
            r = json.loads(raw)
            a, b = r["lines"]
            refs = r["refs"]
            assert isinstance(refs, list) and len(set(refs)) >= 2 and isinstance(r.get("gist"), str)
        except Exception:  # noqa: BLE001
            bad += 1
            continue
        slices += 1
        if b - a + 1 > 150:
            warns.append(f"receipt slice {a}-{b} longer than 150 lines")
        if not all(chunk_refs.get(x) is not None and a <= chunk_refs[x] <= b for x in refs):
            bad += 1  # receipt cites a handle that is not inside the slice it claims to have read
            continue
        covered.update(l for l in lines if a <= l <= b)
    stats["receipt_slices"] = slices
    stats["receipt_coverage"] = round(len(covered) / max(1, len(lines)), 3)
    if bad:
        fails.append(f"{bad} malformed or false reading receipts (refs must be handles that occur in the slice's own lines)")
    if stats["receipt_coverage"] < 0.98:
        fails.append(f"reading receipts cover {stats['receipt_coverage']:.0%} of event lines (need >= 98%)")


def check_lens(d: Path, lens: str, chunk_refs: dict[str, int], n_events: int, store, cfg: dict,
               fails: list[str], warns: list[str], stats: dict) -> None:
    from swarmscope.claims import verify_claims

    tag = lens
    local: list[str] = []
    if not cfg["strict"] and not (d / "v2_changes.json").exists():  # calibration: pilots predate the change log
        v1, vv1, v2, vv2 = (load(d / f, local) for f in ("claims_v1.json", "verified_v1.json", "claims_v2.json", "verified_v2.json"))
        chg = []
    else:
        v1, vv1, v2, chg, vv2 = (load(d / f, local) for f in FILES)
    if local:
        fails += [f"[{tag}] {m}" for m in local]
        return
    st = stats.setdefault(tag, {})

    # -- schema
    claims1, claims2 = v1.get("claims", []), v2.get("claims", [])
    allowed_q = set(LENS_Q.get(lens, []))
    unanswered = v2.get("unanswered", {}) if isinstance(v2.get("unanswered", {}), dict) else {}
    for c in claims2:
        if not (isinstance(c.get("id"), str) and isinstance(c.get("claim"), str) and isinstance(c.get("evidence"), list) and c["evidence"]):
            fails.append(f"[{tag}] claim {c.get('id')} malformed (id/claim/evidence)")
            break
    stray = sorted({c.get("question") for c in claims2} - allowed_q)
    if stray:
        fails.append(f"[{tag}] claims for questions outside this lens: {stray}")
    if cfg["strict"]:
        for c in claims2:
            if c.get("importance") not in (1, 2, 3, 4, 5) or c.get("confidence") not in ("high", "medium", "low"):
                fails.append(f"[{tag}] claim {c.get('id')} needs importance 1-5 and confidence high|medium|low")
                break
        imps = [c.get("importance") for c in claims2]
        if len(set(imps)) == 1 and len(imps) > 10:
            warns.append(f"[{tag}] every claim has the same importance ({imps[0]}): no ranking signal")
        answered = {c.get("question") for c in claims2}
        for q in sorted(allowed_q - answered):
            if len(str(unanswered.get(q, ""))) < 15:
                fails.append(f"[{tag}] {q} has no claims and no `unanswered` reason (>= 15 chars)")

    # -- recompute verification; the worker's verified files must match it exactly
    r1, r2 = verify_claims(store, v1), verify_claims(store, v2)
    for name, agent, rec in (("v1", vv1, r1), ("v2", vv2, r2)):
        if claim_map(agent) != claim_map(rec):
            fails.append(f"[{tag}] FORGED-OR-STALE: verified_{name}.json differs from the recomputation of claims_{name}.json")
    n_claims = len(claims2)
    min_claims = cfg["min_claims"]
    if n_claims < min_claims:
        fails.append(f"[{tag}] only {n_claims} claims (need >= {min_claims} for a chunk of {n_events} events)")
    st.update(claims_v1=len(claims1), claims_v2=n_claims, quote_reject_rate_v1=r1["summary"]["quote_reject_rate"],
              quote_status_v1=r1["summary"]["quote_status"])

    # -- v2 must be fully verified
    bad_status = {k: v for k, v in r2["summary"]["claim_status"].items() if k != "verified"}
    if bad_status:
        fails.append(f"[{tag}] v2 claims not fully verified: {bad_status}")
    flagged = sum(1 for b in r2["batches"] for c in b["claims"] if "actors_unsupported" in c.get("flags", {}))
    st["actors_unsupported_share"] = round(flagged / max(1, n_claims), 3)
    if flagged / max(1, n_claims) > MAX_UNSUPPORTED_ACTOR_SHARE:
        msg = f"[{tag}] {flagged}/{n_claims} claims name actors absent from their evidence (> {MAX_UNSUPPORTED_ACTOR_SHARE:.0%})"
        # structured outreach events do not carry agent names, so on that lens the flag is a data artefact (pilot: 89%)
        (warns if lens == "oversight" else fails).append(msg)

    # -- v1 -> v2 discipline
    ids1, ids2 = {c["id"] for c in claims1 if "id" in c}, {c["id"] for c in claims2 if "id" in c}
    deleted = ids1 - ids2
    logged_del = {x.get("claim_id") for x in chg if isinstance(x, dict) and x.get("kind") == "claim_deleted"}
    if any(not isinstance(x, dict) or x.get("kind") not in CHANGE_KINDS for x in chg):
        fails.append(f"[{tag}] v2_changes.json has entries with unknown `kind`")
    if deleted - logged_del:
        fails.append(f"[{tag}] {len(deleted - logged_del)} claims deleted from v1 without a claim_deleted entry")
    if claims1 and len(deleted) / len(claims1) > MAX_DELETED_SHARE:
        fails.append(f"[{tag}] {len(deleted)}/{len(claims1)} v1 claims deleted (> {MAX_DELETED_SHARE:.0%}): deleting to pass is not repairing")
    m1, m2 = (d / "claims_v1.json").stat().st_mtime, (d / "claims_v2.json").stat().st_mtime
    mv1, mv2 = (d / "verified_v1.json").stat().st_mtime, (d / "verified_v2.json").stat().st_mtime
    if not (m1 <= mv1 + 1 and mv1 <= m2 + 1 and m2 <= mv2 + 1):
        fails.append(f"[{tag}] file order violates v1 -> verified_v1 -> v2 -> verified_v2 (was v1 edited afterwards?)")

    # -- quote quality
    quotes = [(e.get("ref"), e.get("quote", "")) for c in claims2 for e in c.get("evidence", [])]
    words = [len(str(q).split()) for _, q in quotes]
    long_share = sum(w >= LONG_QUOTE_WORDS for w in words) / max(1, len(words))
    st["quotes"] = len(quotes)
    st["quote_words_median"] = sorted(words)[len(words) // 2] if words else 0
    st["long_quote_share"] = round(long_share, 3)
    if long_share < MIN_LONG_QUOTE_SHARE:
        fails.append(f"[{tag}] only {long_share:.0%} of quotes have >= {LONG_QUOTE_WORDS} words (need {MIN_LONG_QUOTE_SHARE:.0%}): short quotes match anything")
    dup = {}
    for q in quotes:
        dup[q] = dup.get(q, 0) + 1
    worst = max(dup.values()) if dup else 0
    if worst > DUP_QUOTE_WARN:
        warns.append(f"[{tag}] one quote reused {worst}x")

    # -- depth: cited events spread over the chunk
    cited = set()
    for b in r2["batches"]:
        for c in b["claims"]:
            for e in c["evidence"]:
                if e.get("status") == "verified":
                    cited.add(ref10(e["event_id"]))
    inside = [chunk_refs[r] for r in cited if r in chunk_refs]
    outside = len(cited) - len(inside)
    lines = sorted(chunk_refs.values())
    quint = {min(4, lines.index(l) * 5 // max(1, len(lines))) for l in inside}
    st["distinct_events_cited"] = len(cited)
    st["quintiles_hit"] = len(quint)
    if outside:
        warns.append(f"[{tag}] {outside} cited events are not in this chunk")
    if len(quint) < MIN_QUINTILES:
        fails.append(f"[{tag}] evidence covers only {len(quint)}/5 parts of the chunk (need >= {MIN_QUINTILES}): the chunk was not read in full")
    if len(cited) < cfg["min_events"]:
        fails.append(f"[{tag}] only {len(cited)} distinct events cited (need >= {cfg['min_events']})")

    # -- soft signals for the reviewer
    for c in claims2:
        cnt = c.get("count")
        if cnt is not None and not (isinstance(cnt, int) and 2 <= cnt <= 12):
            fails.append(f"[{tag}] claim {c.get('id')}: `count` must be an integer 2..12")
            break
        if isinstance(cnt, int):
            text = c.get("claim", "").lower()
            words_n = {2: "two", 3: "three", 4: "four", 5: "five", 6: "six", 7: "seven", 8: "eight", 9: "nine", 10: "ten", 11: "eleven", 12: "twelve"}
            if str(cnt) not in text and words_n[cnt] not in text:
                warns.append(f"[{tag}] claim {c['id']}: count={cnt} is not stated in the claim text")


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("out", nargs="?", type=Path)
    ap.add_argument("--chunk", type=Path)
    ap.add_argument("--baseline", action="store_true")
    ap.add_argument("--calibrate", action="store_true", help="tolerate the old pilot layout/schema; print stats")
    ap.add_argument("--no-receipts", action="store_true")
    ap.add_argument("--no-tripwire", action="store_true")
    args = ap.parse_args()
    if args.baseline:
        write_baseline()
        return 0
    if not args.out or not args.chunk:
        ap.error("need OUT_DIR and --chunk")

    from swarmscope.store import Store

    out, chunk = args.out.resolve(), args.chunk.resolve()
    manifest = json.loads((WORK / "windows" / "manifest.json").read_text(encoding="utf-8"))
    episode = entry = None
    for name, ep in manifest.items():
        for c in ep["chunks"]:
            # manifest paths may come from another machine (the drive is D: on one, E: on the other): re-anchor under this data/work
            tail = c["path"].replace("\\", "/").split("data/work/", 1)[-1]
            if (WORK / tail).resolve() == chunk:
                episode, entry = name, ep
                break
    if not episode:
        print(json.dumps({"verdict": "REJECT", "fails": [f"chunk not in manifest: {chunk}"]}))
        return 2
    lenses = entry["lenses"]
    chunk_refs, n_events = parse_chunk(chunk)
    fails: list[str] = []
    warns: list[str] = []
    stats: dict = {"episode": episode, "chunk": chunk.name, "events": n_events, "lenses": lenses}
    reject: list[str] = []

    # -- tripwire (worker touched the frozen tool, windows, protocol or this script)
    if not args.no_tripwire:
        if not BASELINE.exists():
            fails.append("tripwire baseline missing: operator must run --baseline first")
        else:
            base, now = json.loads(BASELINE.read_text(encoding="utf-8")), tree_hashes()
            changed = sorted(k for k in set(base) | set(now) if base.get(k) != now.get(k))
            if changed:
                reject.append(f"TRIPWIRE: protected files changed: {changed[:6]}")

    # -- v1 fingerprint: fixed at the first acceptance run, must not change afterwards
    state_p = out / "accept_state.json"
    layout_flat = (out / "claims_v2.json").exists()
    if layout_flat and args.calibrate:
        flat_lens = json.loads((out / "claims_v2.json").read_text(encoding="utf-8")).get("lens", "structure")
        lens_dirs = {flat_lens: out}
    else:
        lens_dirs = {lens: (out if layout_flat else out / lens) for lens in lenses}
    if layout_flat and not args.calibrate:
        fails.append("flat layout is only allowed with --calibrate; use <OUT_DIR>/<lens>/")
    if not args.calibrate:
        cur = {lens: sha(d / "claims_v1.json") for lens, d in lens_dirs.items() if (d / "claims_v1.json").exists()}
        if state_p.exists():
            old = json.loads(state_p.read_text(encoding="utf-8"))
            if any(old.get(k) not in (None, v) for k, v in cur.items()):
                reject.append("claims_v1.json changed after an earlier acceptance run (v1 is immutable)")
        else:
            state_p.write_text(json.dumps(cur), encoding="utf-8")

    cfg = {"strict": not args.calibrate,
           "min_claims": max(6, min(20, n_events // 15)),
           "min_events": max(15, min(60, n_events // 9))}  # pilots cite 131-190 distinct events on a 554-event chunk
    if not args.calibrate and not args.no_receipts:
        check_receipts(out, chunk_refs, n_events, fails, warns, stats)

    store = Store(WORK / "snapshot.duckdb", read_only=True)
    for lens, d in lens_dirs.items():
        check_lens(d, lens, chunk_refs, n_events, store, cfg, fails, warns, stats)

    verdict = "REJECT" if reject else "REVISE" if fails else "ACCEPT"
    result = {"verdict": verdict, "fails": reject + fails, "warns": warns, "stats": stats}
    text = json.dumps(result, indent=1, ensure_ascii=False)
    print(text)
    try:
        (out / "acceptance.json").write_text(text, encoding="utf-8")
    except OSError:
        pass
    return {"ACCEPT": 0, "REVISE": 1, "REJECT": 2}[verdict]


if __name__ == "__main__":
    sys.exit(main())
