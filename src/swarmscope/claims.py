"""Batch verification of model-produced claims.

Input (one object or a list of them)::

    {"model": "...", "question": "...",
     "claims": [{"id": "c1", "claim": "...", "evidence": [{"ref": "a3f9c1d2e4", "quote": "..."}]}]}

Every quote is checked by ``evidence.verify_citation`` (no model involved). A claim is ``verified`` only
if it has evidence and *all* of it verifies; ``partial`` if some does; ``rejected`` if none does.
Verified means "the quote exists in the cited event" - whether the quote *supports* the claim is a
separate (semantic) review.
"""

from __future__ import annotations

import collections

from .evidence import verify_citation
from .store import Store

MAX_COUNTED = 12  # larger counts cannot be itemised; the analyst states them as approximate


def _describe(store: Store, event_id: str) -> dict:
    row = store.con.execute(
        """SELECT e.ts, coalesce(a.display_name, e.actor_id), c.name, e.subtype, e.text
           FROM events e LEFT JOIN actors a ON a.actor_id = e.actor_id
           LEFT JOIN channels c ON c.channel_id = e.channel_id WHERE e.event_id = ?""", [event_id]).fetchone()
    return {"ts": row[0].isoformat(), "actor": row[1], "room": row[2], "subtype": row[3], "_text": row[4] or ""} if row else {}


def _aliases(name: str) -> set[str]:
    """Ways an agent is named in chat: "Claude Opus 4.7" -> also "opus 4.7"."""
    n = " ".join(name.lower().split())
    tokens = n.split()
    return {n, *([n[len("claude "):]] if n.startswith("claude ") else []), *([" ".join(tokens[-2:])] if len(tokens) > 2 else [])}


def _unsupported_actors(named: list[str], evidence: list[dict]) -> list[str]:
    """Actors a claim names that neither speak in nor are mentioned by any of its verified evidence."""
    speakers = {(e.get("actor") or "").lower() for e in evidence}
    texts = " ".join(e.get("_text", "").lower() for e in evidence)
    return [a for a in named if a.lower() not in speakers and not any(alias in texts for alias in _aliases(a))]


def _claim_status(statuses: list[str]) -> str:
    if not statuses:
        return "no_evidence"
    ok = statuses.count("verified")
    return "verified" if ok == len(statuses) else "partial" if ok else "rejected"


def verify_claims(store: Store, payload: dict | list) -> dict:
    batches = payload if isinstance(payload, list) else [payload]
    quotes, claims = collections.Counter(), collections.Counter()
    flagged = 0
    out = []
    for batch in batches:
        checked = []
        for claim in batch.get("claims", []):
            evidence = []
            for ev in claim.get("evidence", []):
                check = verify_citation(store, str(ev.get("ref", "")), str(ev.get("quote", "")))
                quotes[check.status] += 1
                evidence.append({"ref": ev.get("ref"), "quote": ev.get("quote"), "status": check.status,
                                 "event_id": check.event_id,
                                 **(_describe(store, check.event_id) if check.status == "verified" else {})})
            status = _claim_status([e["status"] for e in evidence])
            verified_ev = [e for e in evidence if e["status"] == "verified"]
            flags = {}
            if unsupported := _unsupported_actors([a for a in claim.get("actors", []) if isinstance(a, str)], verified_ev):
                flags["actors_unsupported"] = unsupported
            count = claim.get("count")
            if status == "verified" and isinstance(count, int) and 2 <= count <= MAX_COUNTED:
                # a counted claim must cite exactly one event per counted instance
                if len({e["event_id"] for e in evidence}) != count or len(evidence) != count:
                    status = "count_mismatch"
            claims[status] += 1
            flagged += bool(flags)
            span = sorted(e["ts"] for e in verified_ev)
            checked.append({**claim, "status": status, "flags": flags,
                            "derived": {"first_ts": span[0], "last_ts": span[-1]} if span else {},
                            "evidence": [{k: v for k, v in e.items() if k != "_text"} for e in evidence]})
        out.append({**{k: v for k, v in batch.items() if k != "claims"}, "claims": checked})
    n_quotes, n_claims = sum(quotes.values()), sum(claims.values())
    return {
        "summary": {
            "quotes": n_quotes, "quote_status": dict(quotes),
            "quote_reject_rate": round(1 - quotes["verified"] / n_quotes, 4) if n_quotes else None,
            "claims": n_claims, "claim_status": dict(claims), "claims_flagged": flagged,
        },
        "batches": out,
    }


def digest(verified_files: list[dict], label: str = "", min_importance: int = 1) -> list[str]:
    """One line per fully verified claim across verified-claims files: cheap to skim before pulling evidence."""
    lines = []
    for payload in verified_files:
        for batch in payload["batches"]:
            for c in batch["claims"]:
                importance = int(c.get("importance") or 3)
                if c["status"] == "verified" and importance >= min_importance:
                    lines.append(f"[{label} {c.get('id')} | imp {importance} | {c.get('confidence', '?')}] {c['claim']}")
    return lines
