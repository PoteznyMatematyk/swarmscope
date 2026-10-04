"""Window export: a compact one-line-per-event transcript that a model (or a human) can read and cite.

Every line starts with a timestamp and ends with ``{ref}: text``; ``ref`` is the short citation handle
that ``evidence.verify_citation`` resolves back to the full event id. Newlines inside an event are
flattened to `` ⏎ `` (the verifier treats that marker as whitespace). Outreach decisions are labelled
``ADMIN-DECISION->agent`` and carry ``req=<id>`` so they can be matched to their request.
"""

from __future__ import annotations

from collections.abc import Iterator

from .evidence import ref_of, resolve
from .store import Store

TALK = ("AGENT_TALK", "USER_TALK")
_SELECT = """SELECT e.event_id, e.ts, c.kind, c.name, coalesce(a.display_name, e.actor_id, '-'), e.subtype, e.text,
                    substr(json_extract_string(e.extra, '$.outreachApprovalRequestId'), 1, 8)
             FROM events e
             LEFT JOIN channels c ON c.channel_id = e.channel_id
             LEFT JOIN actors a ON a.actor_id = e.actor_id"""


def _in(column: str, values: tuple[str, ...] | list[str] | None, where: list[str], params: list) -> None:
    if values:
        where.append(f"{column} IN ({', '.join('?' * len(values))})")
        params.extend(values)


def _line(row, max_chars: int, mark: str = "") -> str:
    event_id, ts, kind, room, who, subtype, text, request = row
    body = " ⏎ ".join((text or "").replace("\r", "").split("\n"))
    if len(body) > max_chars:
        body = f"{body[:max_chars]}…[+{len(body) - max_chars} chars]"
    if subtype == "OUTREACH_APPROVAL_RESPONSE":
        who = f"ADMIN-DECISION->{who}"
    place = f" #{room}" if kind == "chat_room" else ""
    label = "" if subtype in TALK else f" <{subtype}{f' req={request}' if request else ''}>"
    return f"{mark}[{ts:%m-%d %H:%M:%S}]{place} {who}{label} {{{ref_of(event_id)}}}: {body}"


def export_window(store: Store, source: str, start: str, end: str, *,
                  rooms: list[str] | None = None, subtypes: tuple[str, ...] | list[str] | None = TALK,
                  actors: list[str] | None = None, max_chars: int = 1600) -> Iterator[str]:
    where, params = ["e.source = ?", "e.ts >= ?", "e.ts < ?"], [source, start, end]
    _in("e.subtype", subtypes, where, params)
    _in("c.name", rooms, where, params)
    _in("a.display_name", actors, where, params)
    rows = store.con.execute(f"{_SELECT} WHERE {' AND '.join(where)} ORDER BY e.ts, e.event_id", params).fetchall()

    yield f"# SwarmScope window | source={source} | {start} -> {end} UTC | {len(rows)} events"
    yield '# cite an event as its {ref} plus a VERBATIM quote taken from that line ("⏎" marks a line break)'
    for row in rows:
        yield _line(row, max_chars)


def context_window(store: Store, ref: str, before: int = 15, after: int = 15, max_chars: int = 3000) -> Iterator[str]:
    """The event ``ref`` (marked ``>>``) with its ``before``/``after`` neighbours in the same channel, full text."""
    matches = resolve(store, ref)
    if len(matches) != 1:
        yield f"# cannot resolve {ref!r}: {len(matches)} matches"
        return
    channel, ts = store.con.execute("SELECT channel_id, ts FROM events WHERE event_id = ?", [matches[0]]).fetchone()
    sql = _SELECT + " WHERE e.channel_id IS NOT DISTINCT FROM ? AND {cond} ORDER BY e.ts {order}, e.event_id {order} LIMIT ?"
    prev = store.con.execute(sql.format(cond="(e.ts, e.event_id) < (?, ?)", order="DESC"),
                             [channel, ts, matches[0], before]).fetchall()[::-1]
    rest = store.con.execute(sql.format(cond="(e.ts, e.event_id) >= (?, ?)", order="ASC"),
                             [channel, ts, matches[0], after + 1]).fetchall()
    yield f"# context of {{{ref_of(matches[0])}}} (>> marks it): {len(prev)} before, {len(rest) - 1} after"
    for row in prev:
        yield _line(row, max_chars)
    for i, row in enumerate(rest):
        yield _line(row, max_chars, ">> " if i == 0 else "")
