"""Propagation tracer: which units of information spread from a first appearance to other actors.

A *unit* is a concrete, quotable token: a URL, a file name, a backticked span, or a code-like identifier
(snake_case, CamelCase, SCREAMING_SNAKE). Everything is deterministic - no model is involved - and each hop
carries the raw matched string, which is a verbatim substring of the cited event, so every hop is a
citation that ``evidence.verify_citation`` accepts.

A *cascade* starts at a unit's first appearance in the whole source history (novelty is judged against
everything earlier, not just the analysed window) and counts the other actors that use the unit within
``horizon_days``. ``burst`` = share of all uses that fall inside that horizon: near 1 for a meme that flared
and died, near 0 for something used all year.
"""

from __future__ import annotations

import re
from collections import defaultdict
from collections.abc import Iterator
from dataclasses import asdict, dataclass, field
from datetime import datetime, timedelta

from .store import Store

_TRAIL = ".,;:!?)]}\"'"
MIN_UNIT = 8  # same floor as evidence.MIN_QUOTE_CHARS: every hop must be an acceptable citation
_URL = re.compile(r"https?://[^\s<>\"'`)\]}]+")
_FILE = re.compile(r"\b[\w-]+(?:\.[\w-]+)*\.(?:py|mjs|js|tsx|ts|html|css|json|md|sh|ya?ml|csv|txt|svg|png)\b")
_CODE = re.compile(r"`([^`\n]{8,60})`")
_SNAKE = re.compile(r"\b[a-z][a-z0-9]*(?:_[a-z0-9]+)+\b")
_CAMEL = re.compile(r"\b[A-Z][a-z0-9]+(?:[A-Z][a-z0-9]+)+\b")
_SCREAM = re.compile(r"\b[A-Z][A-Z0-9]*(?:_[A-Z0-9]+)+\b")


def extract_units(text: str) -> Iterator[tuple[str, str, str]]:
    """Yield ``(kind, key, raw)``: ``key`` is the normalised unit, ``raw`` the exact matched substring."""
    for m in _URL.finditer(text):
        raw = m.group(0).rstrip(_TRAIL)
        key = re.sub(r"^https?://(www\.)?", "", raw).split("?")[0].split("#")[0].rstrip("/").lower()
        if len(key) >= 8:
            yield "url", key, raw
    for m in _FILE.finditer(text):
        before = text[m.start() - 1] if m.start() else " "
        if len(m.group(0)) >= MIN_UNIT and before not in "/.%":  # skip url/path tails and %2F debris
            yield "file", m.group(0).lower(), m.group(0)
    for m in _CODE.finditer(text):
        yield "code", m.group(1).strip().lower(), m.group(1)
    for kind, pattern in (("snake", _SNAKE), ("camel", _CAMEL), ("scream", _SCREAM)):
        for m in pattern.finditer(text):
            if len(m.group(0)) >= MIN_UNIT:
                yield kind, m.group(0) if kind != "snake" else m.group(0).lower(), m.group(0)


@dataclass
class Hop:
    event_id: str
    ts: str
    actor: str
    raw: str          # verbatim substring of the cited event
    lag_hours: float  # since the origin


@dataclass
class Cascade:
    unit: str
    kind: str
    origin: Hop
    adopters: list[Hop] = field(default_factory=list)   # first use by each other actor inside the horizon
    uses_total: int = 0
    uses_in_horizon: int = 0
    burst: float = 0.0
    median_lag_hours: float | None = None


def trace(store: Store, source: str, *, start: str | None = None, end: str | None = None,
          subtypes: list[str] | None = None, horizon_days: float = 7.0, min_adopters: int = 3,
          min_burst: float = 0.5, top: int = 50, kinds: set[str] | None = None) -> list[Cascade]:
    """Rank cascades whose origin lies in ``[start, end)``; history before ``start`` only defines novelty."""
    where, params = ["source = ?", "text IS NOT NULL", "actor_id IS NOT NULL"], [source]
    if subtypes:
        where.append(f"subtype IN ({', '.join('?' * len(subtypes))})")
        params += subtypes
    uses: dict[tuple[str, str], list[tuple[datetime, str, str, str]]] = defaultdict(list)
    cur = store.con.execute(
        f"SELECT e.ts, e.event_id, e.actor_id, coalesce(a.display_name, e.actor_id), e.text FROM events e "
        f"LEFT JOIN actors a ON a.actor_id = e.actor_id WHERE {' AND '.join('e.' + w for w in where)} "
        "AND e.ts IS NOT NULL ORDER BY e.ts, e.event_id", params)
    label: dict[str, str] = {}
    while rows := cur.fetchmany(20000):
        for ts, event_id, actor, name, text in rows:
            label[actor] = name
            seen = set()
            for kind, key, raw in extract_units(text):
                if (kinds and kind not in kinds) or (kind, key) in seen:
                    continue
                seen.add((kind, key))
                uses[(kind, key)].append((ts, event_id, actor, raw))

    lo = datetime.fromisoformat(start + "T00:00:00+00:00") if start else None
    hi = datetime.fromisoformat(end + "T00:00:00+00:00") if end else None
    horizon = timedelta(days=horizon_days)
    cascades = []
    for (kind, key), occ in uses.items():
        t0, e0, a0, raw0 = occ[0]
        if (lo and t0 < lo) or (hi and t0 >= hi):
            continue
        first_by_actor: dict[str, tuple] = {}
        in_horizon = 0
        for ts, event_id, actor, raw in occ:
            if ts - t0 > horizon:
                break
            in_horizon += 1
            if actor != a0 and actor not in first_by_actor:
                first_by_actor[actor] = (ts, event_id, actor, raw)
        if len(first_by_actor) < min_adopters:
            continue
        burst = in_horizon / len(occ)
        if burst < min_burst:
            continue
        hop = lambda ts, eid, actor, raw: Hop(eid, ts.isoformat(), label[actor], raw, round((ts - t0).total_seconds() / 3600, 2))
        adopters = [hop(*v) for v in first_by_actor.values()]
        lags = sorted(h.lag_hours for h in adopters)
        cascades.append(Cascade(unit=key, kind=kind, origin=hop(t0, e0, a0, raw0), adopters=adopters,
                                uses_total=len(occ), uses_in_horizon=in_horizon, burst=round(burst, 3),
                                median_lag_hours=lags[len(lags) // 2]))
    cascades.sort(key=lambda c: (-len(c.adopters), c.median_lag_hours or 0))
    return cascades[:top]


def to_json(cascades: list[Cascade]) -> list[dict]:
    return [asdict(c) for c in cascades]
