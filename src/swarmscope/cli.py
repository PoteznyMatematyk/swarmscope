"""Command line entry point.

    swarmscope ingest collusion_wiki --raw ../data/raw/collusion_wiki
    swarmscope ingest ai_village     --raw ../data/raw/ai_village [--turns]
    swarmscope stats
    swarmscope inspect --raw ../data/raw/ai_village     # print columns of every jsonl(.gz)
    swarmscope cite <event_id> "<quote>"
"""

from __future__ import annotations

import argparse
import collections
import glob
import json
import os
import random
import time
from pathlib import Path

from .adapters import ADAPTERS
from .adapters._io import read_jsonl
from .claims import digest, verify_claims
from .evidence import verify_citation
from .export import context_window, export_window
from .propagation import to_json, trace
from .report import build_report
from .store import Store
from .turns import actions, ingest_turns, memories, open_turns, verify_turn_quote

DEFAULT_DB = Path(__file__).resolve().parents[3] / "data" / "swarm.duckdb"
DEFAULT_DAY_MAP = DEFAULT_DB.parent / "day_map.json"
DEFAULT_TURNS_DB = Path(os.environ.get("SWARMSCOPE_TURNS_DB") or DEFAULT_DB.parent / "turns.duckdb")  # frozen run.py sets the env var


def cmd_ingest(args, store: Store) -> None:
    adapter = ADAPTERS[args.source]
    raw = Path(args.raw)
    t0 = time.perf_counter()
    store.clear_source(args.source)
    n_ch = store.add_channels(adapter.channels(raw))
    n_ac = store.add_actors(adapter.actors(raw))
    kwargs = {"include_turns": args.turns} if args.source == "ai_village" else {}
    n_ev = store.add_events(adapter.events(raw, **kwargs))
    stored = store.con.execute("SELECT count(*) FROM events WHERE source = ?", [args.source]).fetchone()[0]
    lost = f"  !! {n_ev - stored} lost to duplicate event_id" if stored != n_ev else ""
    print(f"{args.source}: {n_ev} events, {n_ac} actors, {n_ch} channels "
          f"in {time.perf_counter() - t0:.1f}s -> {store.path}{lost}")


def cmd_stats(args, store: Store) -> None:
    print(f"{'source':<16}{'type':<10}{'subtype':<34}{'n':>8}{'actors':>8}{'channels':>9}  first -> last")
    for src, et, sub, n, a, c, first, last in store.stats():
        print(f"{src:<16}{et:<10}{sub:<34}{n:>8}{a:>8}{c:>9}  {first} -> {last}")


def cmd_inspect(args, store: Store | None = None) -> None:
    for path in sorted(Path(args.raw).glob("*.jsonl*")):
        cols: collections.Counter = collections.Counter()
        n = 0
        for n, rec in read_jsonl(path):
            cols.update(rec.keys())
            if n >= args.sample:
                break
        print(f"== {path.name} (first {n} rows)")
        for k, v in cols.most_common():
            print(f"   {k:<32}{v}")


def cmd_cite(args, store: Store) -> None:
    print(verify_citation(store, args.event_id, args.quote))


def cmd_export(args, store: Store) -> None:
    split = lambda s: [x.strip() for x in s.split(",") if x.strip()] if s else None
    lines = list(export_window(store, args.source, args.start, args.end, rooms=split(args.rooms),
                               subtypes=split(args.subtypes), actors=split(args.actors),
                               max_chars=args.max_chars))
    Path(args.out).parent.mkdir(parents=True, exist_ok=True)
    Path(args.out).write_text("\n".join(lines) + "\n", encoding="utf-8")
    chars = sum(len(x) for x in lines)
    print(f"{len(lines) - 2} events, {chars:,} chars (~{chars // 4:,} tokens) -> {args.out}")


def cmd_context(args, store: Store) -> None:
    print("\n".join(context_window(store, args.ref, args.before, args.after, args.max_chars)))


def _label(verified_file: str) -> str:
    """Claim-set label: ``<chunk folder>/<lens>`` for the packet layout (OUT/<lens>/verified_v2.json), else the folder name."""
    p = Path(verified_file).parent
    return f"{p.parent.name}/{p.name}" if p.name in ("structure", "friction", "oversight") else p.name


def cmd_digest(args, store: Store) -> None:
    lines = []
    for pattern in args.files:
        for f in sorted(glob.glob(pattern)):
            label = _label(f)
            lines += digest([json.loads(Path(f).read_text(encoding="utf-8"))], label, args.min_importance)
    print("\n".join(lines))


def cmd_verify_findings(args, store: Store) -> None:
    failing = 0
    turns = open_turns(args.turns_db) if Path(args.turns_db).exists() else None
    for f in json.loads(Path(args.file).read_text(encoding="utf-8")):
        checks = [(key, e, verify_citation(store, str(e.get("ref", "")), str(e.get("quote", ""))).status)
                  for key in ("evidence", "counter_evidence") for e in f.get(key, [])]
        # `did_evidence`: (turn ref, quote) pairs from `actions` - what the agent executed, checked against the turns database
        checks += [("did_evidence", e, verify_turn_quote(turns, str(e.get("ref", "")), str(e.get("quote", ""))) if turns else "no_turns_db")
                   for e in f.get("did_evidence", [])]
        fails = [(key, e.get("ref"), status) for key, e, status in checks if status != "verified"]
        failing += bool(fails)
        print(f"{f.get('id')}: {len(checks) - len(fails)}/{len(checks)} verified" + (f"  FAIL {fails}" if fails else ""))
    print(f"{failing} finding(s) with failing evidence")


def cmd_audit_sample(args, store: Store) -> None:
    pool = []
    for pattern in args.files:
        for f in sorted(glob.glob(pattern)):
            for batch in json.loads(Path(f).read_text(encoding="utf-8"))["batches"]:
                pool += [(_label(f), c) for c in batch["claims"] if c["status"] == "verified"]
    random.Random(args.seed).shuffle(pool)
    print(f"# audit sample: {len(pool[args.offset:args.offset + args.n])} of {len(pool)} verified claims (seed {args.seed})")
    for label, c in pool[args.offset:args.offset + args.n]:
        print(f"\n=== [{label} {c['id']}] importance {c.get('importance')} confidence {c.get('confidence')}")
        print(f"CLAIM: {c['claim']}\nACTORS: {c.get('actors')}\nNOTES: {c.get('notes') or '-'}")
        for i, e in enumerate(c["evidence"], 1):
            print(f"--- evidence {i}: ref {e['ref']} quote: \"{e['quote']}\"")
            print("\n".join(context_window(store, e["ref"], args.context, args.context, args.max_chars)))


def cmd_trace(args, store: Store) -> None:
    split = lambda s: [x.strip() for x in s.split(",") if x.strip()] if s else None
    found = trace(store, args.source, start=args.start, end=args.end, subtypes=split(args.subtypes),
                  horizon_days=args.horizon_days, min_adopters=args.min_adopters, min_burst=args.min_burst,
                  top=args.top, kinds=set(split(args.kinds) or []) or None)
    if args.out:
        Path(args.out).write_text(json.dumps(to_json(found), ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"{'unit':<46}{'kind':<7}{'adopt':>6}{'uses':>6}{'burst':>6}{'med.lag h':>10}  origin")
    for c in found:
        print(f"{c.unit[:45]:<46}{c.kind:<7}{len(c.adopters):>6}{c.uses_total:>6}{c.burst:>6}"
              f"{c.median_lag_hours:>10}  {c.origin.ts[:16]} {c.origin.actor[:28]}")


def cmd_report(args, store: Store) -> None:
    load = lambda f: json.loads(Path(f).read_text(encoding="utf-8"))
    files = lambda pattern: [load(f) for pat in (pattern or []) for f in sorted(glob.glob(pat))]
    day_map = load(args.day_map) if Path(args.day_map).exists() else None
    report = build_report(
        store, meta={"title": args.title, "source": args.source}, batches=files(args.claims),
        first_pass=files(args.first_pass) or None, day_map=day_map,
        findings=load(args.findings) if args.findings else None,
        cascades=load(args.trace) if args.trace else None,
        turns=open_turns(args.turns_db) if Path(args.turns_db).exists() else None)
    Path(args.out).write_text(json.dumps(report, ensure_ascii=False, indent=1), encoding="utf-8")
    print(json.dumps(report["metrics"], ensure_ascii=False))


def cmd_verify_claims(args, store: Store) -> None:
    result = verify_claims(store, json.loads(Path(args.file).read_text(encoding="utf-8")))
    if args.out:
        Path(args.out).write_text(json.dumps(result, ensure_ascii=False, indent=1), encoding="utf-8")
    print(json.dumps(result["summary"], ensure_ascii=False))


def cmd_viewer(args) -> None:
    """Embed a report.json into the offline Evidence Viewer (viewer/embed.py) -> one self-contained HTML file."""
    import importlib.util
    import sys

    embed = Path(__file__).resolve().parents[2] / "viewer" / "embed.py"
    spec = importlib.util.spec_from_file_location("swarmscope_viewer_embed", embed)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    sys.exit(mod.main(["--report", args.report, "--out", args.out]))


def cmd_saydo(args, store: Store) -> None:
    from .saydo import _test_runs, audit_test_claims

    turns = open_turns(args.turns_db)
    runs = _test_runs(turns)
    results = {w: audit_test_claims(store, turns, w, args.source, runs) for w in args.window_hours}
    main_w = args.window_hours[0]
    res = results[main_w]
    res["sensitivity"] = {str(w): r["summary"]["by_category"] for w, r in results.items()}
    if args.out:
        Path(args.out).write_text(json.dumps(res, ensure_ascii=False, indent=1, default=str), encoding="utf-8")
    print(f"window {main_w} h: {res['claims']} test-success claims; {json.dumps(res['summary']['by_category'])}; "
          f"contradicted/judged = {res['summary']['contradicted_share_of_judged']} (n={res['summary']['judged']})")
    for w, cats in res["sensitivity"].items():
        print(f"  window {w} h: {cats}")
    for r in [r for r in res["rows"] if r["category"] in ("contradicted", "subagent_report_only", "stale_green")][: args.examples]:
        run, sub = r.get("evidence_run"), r.get("subagent_report")
        print(f"- {r['category']} [{r['ts'][:16]}] {r['agent']} {{{r['event_ref']}}} \"{r['claim_quote'][:110]}\"")
        if run:
            print(f"    own run {run['lag_min']} min earlier {{{run['ref']}}}: \"{run['quote']}\" ({r['red_runs']} red / {r['parsed_runs']} parsed runs in window)")
        if sub:
            print(f"    sub-agent report {sub['lag_min']} min earlier {{{sub['ref']}}}")


def cmd_ingest_turns(args) -> None:
    print(json.dumps(ingest_turns(Path(args.raw), Path(args.out)), ensure_ascii=False))


def cmd_actions(args) -> None:
    split = lambda s: [x.strip() for x in s.split(",") if x.strip()] if s else None
    print("\n".join(actions(open_turns(args.turns_db), args.agent, args.start, args.end, split(args.types), args.grep, args.limit, args.max_chars)))


def cmd_memories(args) -> None:
    print("\n".join(memories(open_turns(args.turns_db), args.agent, args.start, args.end, args.grep, args.limit, args.max_chars)))


def cmd_cite_turn(args) -> None:
    print(verify_turn_quote(open_turns(args.turns_db), args.ref, args.quote))


def main(argv: list[str] | None = None) -> None:
    p = argparse.ArgumentParser(prog="swarmscope")
    p.add_argument("--db", default=str(DEFAULT_DB))
    sub = p.add_subparsers(dest="cmd", required=True)

    s = sub.add_parser("ingest")
    s.add_argument("source", choices=sorted(ADAPTERS))
    s.add_argument("--raw", required=True)
    s.add_argument("--turns", action="store_true", help="ai_village: include computer_use_turns (~1.1M)")
    s.set_defaults(fn=cmd_ingest)

    sub.add_parser("stats").set_defaults(fn=cmd_stats)

    s = sub.add_parser("inspect")
    s.add_argument("--raw", required=True)
    s.add_argument("--sample", type=int, default=2000)
    s.set_defaults(fn=cmd_inspect, no_store=True)

    s = sub.add_parser("cite")
    s.add_argument("event_id")
    s.add_argument("quote")
    s.set_defaults(fn=cmd_cite)

    s = sub.add_parser("export", help="write a time window as a citable one-line-per-event transcript")
    s.add_argument("--source", default="ai_village")
    s.add_argument("--start", required=True, help="inclusive, e.g. 2026-06-01")
    s.add_argument("--end", required=True, help="exclusive, e.g. 2026-06-08")
    s.add_argument("--rooms", help="comma-separated chat room names")
    s.add_argument("--subtypes", default="AGENT_TALK,USER_TALK", help="comma-separated; empty = all")
    s.add_argument("--actors", help="comma-separated display names")
    s.add_argument("--max-chars", type=int, default=1200)
    s.add_argument("--out", required=True)
    s.set_defaults(fn=cmd_export)

    s = sub.add_parser("context", help="show an event with its neighbours in the same channel (full text)")
    s.add_argument("ref")
    s.add_argument("--before", type=int, default=15)
    s.add_argument("--after", type=int, default=15)
    s.add_argument("--max-chars", type=int, default=3000)
    s.set_defaults(fn=cmd_context)

    s = sub.add_parser("digest", help="one line per verified claim from verified_*.json files (globs)")
    s.add_argument("files", nargs="+")
    s.add_argument("--min-importance", type=int, default=1)
    s.set_defaults(fn=cmd_digest)

    s = sub.add_parser("verify-findings", help="check the evidence of a curated findings JSON (events; and turns via did_evidence)")
    s.add_argument("file")
    s.add_argument("--turns-db", default=str(DEFAULT_TURNS_DB))
    s.set_defaults(fn=cmd_verify_findings)

    s = sub.add_parser("audit-sample", help="random verified claims with full event context, for semantic audit")
    s.add_argument("files", nargs="+", help="verified_*.json files or globs")
    s.add_argument("--n", type=int, default=30)
    s.add_argument("--offset", type=int, default=0)
    s.add_argument("--seed", type=int, default=1)
    s.add_argument("--context", type=int, default=3)
    s.add_argument("--max-chars", type=int, default=1800)
    s.set_defaults(fn=cmd_audit_sample)

    s = sub.add_parser("trace", help="rank units (urls, files, identifiers) that spread between actors")
    s.add_argument("--source", default="ai_village")
    s.add_argument("--start", help="only cascades whose first appearance is on/after this date")
    s.add_argument("--end")
    s.add_argument("--subtypes", help="comma-separated event subtypes to scan (default: all with text)")
    s.add_argument("--kinds", help="comma-separated: url,file,code,snake,camel,scream")
    s.add_argument("--horizon-days", type=float, default=7.0)
    s.add_argument("--min-adopters", type=int, default=3)
    s.add_argument("--min-burst", type=float, default=0.5)
    s.add_argument("--top", type=int, default=40)
    s.add_argument("--out")
    s.set_defaults(fn=cmd_trace)

    s = sub.add_parser("report", help="assemble report.json (re-verifies every quote, adds context and deep links)")
    s.add_argument("--source", default="ai_village")
    s.add_argument("--title", default="SwarmScope report")
    s.add_argument("--claims", nargs="*", help="claim files or globs (final, repaired)")
    s.add_argument("--first-pass", nargs="*", help="unrepaired claim files or globs (misquote statistics)")
    s.add_argument("--trace", help="JSON written by `trace --out`")
    s.add_argument("--findings", help="curated findings JSON")
    s.add_argument("--day-map", default=str(DEFAULT_DAY_MAP))
    s.add_argument("--turns-db", default=str(DEFAULT_TURNS_DB), help="layer C database; verifies did_evidence of findings")
    s.add_argument("--out", required=True)
    s.set_defaults(fn=cmd_report)

    s = sub.add_parser("verify-claims", help="check every (ref, quote) of a claims JSON against the store")
    s.add_argument("file")
    s.add_argument("--out")
    s.set_defaults(fn=cmd_verify_claims)

    s = sub.add_parser("saydo", help="said vs did: chat claims of passing tests vs the agent's own executed test runs")
    s.add_argument("--source", default="ai_village")
    s.add_argument("--window-hours", type=float, nargs="+", default=[2.0, 1.0, 6.0], help="first = main window, others = sensitivity")
    s.add_argument("--turns-db", default=str(DEFAULT_TURNS_DB))
    s.add_argument("--examples", type=int, default=12)
    s.add_argument("--out")
    s.set_defaults(fn=cmd_saydo)

    s = sub.add_parser("viewer", help="embed report.json into the offline Evidence Viewer -> one self-contained HTML")
    s.add_argument("--report", required=True)
    s.add_argument("--out", required=True)
    s.set_defaults(fn=cmd_viewer, no_store=True)

    s = sub.add_parser("ingest-turns", help="layer C: slim turns + memories database from the raw jsonl.gz (no raw model messages)")
    s.add_argument("--raw", required=True)
    s.add_argument("--out", default=str(DEFAULT_TURNS_DB))
    s.set_defaults(fn=cmd_ingest_turns, no_store=True)

    s = sub.add_parser("actions", help="what an agent DID: executed computer-use turns in a UTC window")
    s.add_argument("--agent", required=True, help="display name or a part of it")
    s.add_argument("--start", required=True, help="inclusive UTC, e.g. 2026-06-01T10:00")
    s.add_argument("--end", required=True, help="exclusive UTC")
    s.add_argument("--types", help="comma-separated action types, e.g. bash,type,key")
    s.add_argument("--grep", help="case-insensitive substring of the action or its output")
    s.add_argument("--limit", type=int, default=200)
    s.add_argument("--max-chars", type=int, default=300)
    s.add_argument("--turns-db", default=str(DEFAULT_TURNS_DB))
    s.set_defaults(fn=cmd_actions, no_store=True)

    s = sub.add_parser("memories", help="long-term memories an agent wrote in a UTC window")
    s.add_argument("--agent", required=True)
    s.add_argument("--start", required=True)
    s.add_argument("--end", required=True)
    s.add_argument("--grep")
    s.add_argument("--limit", type=int, default=50)
    s.add_argument("--max-chars", type=int, default=1200)
    s.add_argument("--turns-db", default=str(DEFAULT_TURNS_DB))
    s.set_defaults(fn=cmd_memories, no_store=True)

    s = sub.add_parser("cite-turn", help="verify a quote against one turn (action text, output or error)")
    s.add_argument("ref")
    s.add_argument("quote")
    s.add_argument("--turns-db", default=str(DEFAULT_TURNS_DB))
    s.set_defaults(fn=cmd_cite_turn, no_store=True)

    args = p.parse_args(argv)
    if getattr(args, "no_store", False):
        args.fn(args)
    else:
        args.fn(args, Store(args.db, read_only=args.cmd != "ingest"))


if __name__ == "__main__":
    main()
