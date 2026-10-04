"""Assemble ``report.json`` - the single contract between the analysis and the evidence viewer.

Every piece of evidence is re-verified here against the store (never trusted from an input file) and enriched
with who/when/where, the full event text, the character span of the quote and a link into the live viewer.

    report = {meta, metrics, findings[], claims[], cascades[]}
    evidence = {ref, event_id, status, ts, actor, room, subtype, quote, context, span, deeplink}
"""

from __future__ import annotations

import re
from datetime import datetime

from .claims import verify_claims
from .evidence import verify_citation
from .links import deeplink
from .store import Store
from .turns import get_turn, verify_turn_quote

_CHARS = {"‘": "'", "’": "'", "“": '"', "”": '"', " ": " ", "⏎": " "}
CONTEXT_CHARS = 4000      # per cited event
HOP_CONTEXT_CHARS = 500   # per cascade hop (cascades can have hundreds)
MAX_HOPS = 40             # adopters embedded per cascade (n_adopters keeps the true count)


def _fold(text: str) -> str:
    return "".join(_CHARS.get(c, c) for c in text)   # 1:1 char map, so offsets stay valid


def locate(text: str, quote: str) -> list[int] | None:
    """Best-effort ``[start, end)`` of ``quote`` inside ``text`` (whitespace and quote style tolerant)."""
    words = _fold(quote).split()
    if not words:
        return None
    m = re.search(r"\s+".join(map(re.escape, words)), _fold(text), re.I)
    return [m.start(), m.end()] if m else None


def _event(store: Store, event_id: str) -> dict:
    row = store.con.execute(
        """SELECT e.ts, coalesce(a.display_name, e.actor_id), c.name, e.subtype, e.text
           FROM events e LEFT JOIN actors a ON a.actor_id = e.actor_id
           LEFT JOIN channels c ON c.channel_id = e.channel_id WHERE e.event_id = ?""", [event_id]).fetchone()
    return {"ts": row[0], "actor": row[1], "room": row[2], "subtype": row[3], "text": row[4] or ""} if row else {}


def evidence(store: Store, ref: str, quote: str, day_map: dict[str, int] | None = None,
             context_chars: int = CONTEXT_CHARS) -> dict:
    check = verify_citation(store, ref, quote)
    out = {"ref": ref, "event_id": check.event_id, "status": check.status, "quote": quote}
    if check.status == "verified":
        ev = _event(store, check.event_id)
        text = ev["text"]
        span = locate(text, quote)
        start = max(0, (span[0] if span else 0) - context_chars // 2)
        out.update(ts=ev["ts"].isoformat(), actor=ev["actor"], room=ev["room"], subtype=ev["subtype"],
                   context=text[start:start + context_chars], context_offset=start,
                   span=[span[0] - start, span[1] - start] if span else None,
                   deeplink=deeplink(ev["ts"], day_map) if day_map else None)
    return out


def turn_evidence(turns, ref: str, quote: str, day_map: dict[str, int] | None = None) -> dict:
    """Evidence item for an executed computer-use turn ("did"): same shape as ``evidence`` so the viewer shows it unchanged."""
    status = verify_turn_quote(turns, ref, quote) if turns is not None else "no_turns_db"
    out = {"ref": ref, "event_id": None, "status": status, "quote": quote, "kind": "turn"}
    if status == "verified":
        t = get_turn(turns, ref)
        text = (f"{t['action_type']}: {t['action_text']}" + (f"\n\n[output]\n{t['out_text']}" if t["out_text"] else "")
                + (f"\n\n[output, end]\n{t['out_tail']}" if t.get("out_tail") else "") + (f"\n\n[error]\n{t['err_text']}" if t["err_text"] else ""))
        span = locate(text, quote)
        out.update(event_id=t["turn_id"], ts=t["ts"].isoformat(), actor=t["agent"], room="computer-use", subtype=t["action_type"],
                   context=text[:CONTEXT_CHARS], context_offset=0, span=span,
                   deeplink=deeplink(t["ts"], day_map) if day_map else None)
    return out


def hop(store: Store, h: dict, day_map: dict[str, int] | None) -> dict:
    ev = evidence(store, h["event_id"], h["raw"], day_map, HOP_CONTEXT_CHARS)
    return {**{k: h[k] for k in ("event_id", "ts", "actor", "raw", "lag_hours")}, "status": ev["status"],
            "deeplink": ev.get("deeplink"), "context": ev.get("context"), "span": ev.get("span")}


def build_report(store: Store, *, meta: dict, batches: list[dict] | None = None, findings: list[dict] | None = None,
                 cascades: list[dict] | None = None, day_map: dict[str, int] | None = None,
                 first_pass: list[dict] | None = None, turns=None) -> dict:
    """``batches``: claim batches (see ``claims``); ``findings``: curated items whose ``evidence`` is [{ref, quote}]
    (plus optional ``counter_evidence`` and ``did_evidence``, the latter checked against the turns database ``turns``
    and merged into ``evidence`` with role ``did``); ``cascades``: ``propagation.to_json`` output; ``first_pass``:
    unrepaired claim batches, only used to report how often models misquote before repair."""
    verified = verify_claims(store, batches or [])
    claims = []
    for batch in verified["batches"]:
        for c in batch["claims"]:
            claims.append({**{k: c.get(k) for k in ("id", "question", "claim", "actors", "first_ts", "confidence", "importance", "count", "notes", "flags", "derived")},
                           "status": c["status"], "model": batch.get("model"), "lens": batch.get("lens"),
                           "chunk": batch.get("chunk"),
                           "evidence": [evidence(store, e["ref"], e["quote"], day_map) for e in c["evidence"]]})
    out_findings = []
    for f in findings or []:
        item = {k: v for k, v in f.items() if k not in ("evidence", "counter_evidence", "did_evidence")}
        for key in ("evidence", "counter_evidence"):
            item[key] = [evidence(store, e["ref"], e["quote"], day_map) | {"role": e.get("role")}
                         for e in f.get(key, [])]
        item["evidence"] += [turn_evidence(turns, e["ref"], e["quote"], day_map) | {"role": "did"} for e in f.get("did_evidence", [])]
        item["all_verified"] = all(e["status"] == "verified" for k in ("evidence", "counter_evidence") for e in item[k])
        out_findings.append(item)
    metrics = {"final": verified["summary"]}
    if first_pass:
        first = verify_claims(store, first_pass)
        metrics["first_pass"] = first["summary"]
        by_model: dict[str, dict] = {}
        for batch in first["batches"]:
            m = by_model.setdefault(batch.get("model") or "?", {"quotes": 0, "verified": 0})
            for c in batch["claims"]:
                m["quotes"] += len(c["evidence"])
                m["verified"] += sum(e["status"] == "verified" for e in c["evidence"])
        metrics["first_pass_by_model"] = {
            k: {**v, "reject_rate": round(1 - v["verified"] / v["quotes"], 4) if v["quotes"] else None}
            for k, v in by_model.items()}
    cas = [{**c, "n_adopters": len(c["adopters"]), "origin": hop(store, c["origin"], day_map),
            "adopters": [hop(store, h, day_map) for h in c["adopters"][:MAX_HOPS]]} for c in cascades or []]
    hops = [h for c in cas for h in [c["origin"], *c["adopters"]]]
    metrics["tracer"] = {"hops": len(hops), "hops_rejected": sum(h["status"] != "verified" for h in hops)}
    return {"meta": {**meta, "generated": datetime.now().astimezone().isoformat(timespec="seconds")},
            "metrics": metrics, "findings": out_findings, "claims": claims, "cascades": cas}
