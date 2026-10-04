"""Adapter for the public collusion.wiki export (https://collusion.wiki/explorer/download).

Files used: pages.jsonl, revisions.jsonl, events.jsonl, labels.jsonl.
Actors are the self-given agent labels; an empty label means the edit carried
no name (ip16 is kept in ``extra`` as a weak grouping signal).
"""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

from ..schema import Actor, Channel, Event
from ._io import find, parse_ts, read_jsonl

SOURCE = "collusion_wiki"


def _actor_id(label: str | None) -> str:
    return f"{SOURCE}:label:{label}" if label else f"{SOURCE}:label:<unnamed>"


def _channel_id(page_key: str) -> str:
    return f"{SOURCE}:page:{page_key}"


def channels(raw_dir: Path) -> Iterator[Channel]:
    path = find(raw_dir, "pages.jsonl")
    for _, p in read_jsonl(path):
        yield Channel(
            channel_id=_channel_id(p["page_key"]), source=SOURCE, kind="wiki_page", name=p["name"],
            extra={k: p.get(k) for k in ("wiki", "page_family", "n_revs", "first_write",
                                         "last_write", "n_deletions", "n_labels")},
        )


def actors(raw_dir: Path) -> Iterator[Actor]:
    path = find(raw_dir, "labels.jsonl")
    for _, a in read_jsonl(path):
        yield Actor(
            actor_id=_actor_id(a["label"]), source=SOURCE,
            kind="human" if a.get("is_human_handle") else "agent",
            display_name=a["label"] or None,
            extra={k: a.get(k) for k in ("stored_revisions", "first_write", "last_write",
                                         "wikis", "save_requests")},
        )


def events(raw_dir: Path) -> Iterator[Event]:
    rev_path = find(raw_dir, "revisions.jsonl")
    for lineno, r in read_jsonl(rev_path):
        seq = r["seq"]
        yield Event(
            event_id=f"{SOURCE}:rev:{r['rev_id']}", source=SOURCE, ts=parse_ts(r["time"]),
            ts_uncertainty_s=r.get("uncertainty_seconds"), actor_id=_actor_id(r.get("label")),
            channel_id=_channel_id(r["page_key"]), event_type="edit", text=r.get("body"),
            parent_id=f"{SOURCE}:rev:{r['page_key']}@{seq - 1}" if seq > 1 else None,
            raw_ref=f"{rev_path.name}:{lineno}",
            extra={"ip16": r.get("ip16"), "time_grade": r.get("time_grade"), "wiki": r.get("wiki"),
                   "change_summary": r.get("change_summary")},
        )

    ev_path = find(raw_dir, "events.jsonl")
    for lineno, e in read_jsonl(ev_path):
        etype = e["event_type"]
        if etype == "save":  # already represented by revisions (with body)
            continue
        page_key = e.get("page_key")
        yield Event(
            event_id=f"{SOURCE}:ev:{e['event_id']}", source=SOURCE, ts=parse_ts(e.get("time")),
            ts_uncertainty_s=e.get("uncertainty_seconds"),
            actor_id=_actor_id(e.get("actor_label")) if "actor_label" in e else None,
            channel_id=_channel_id(page_key) if page_key else None,
            event_type={"delete": "deletion", "revert": "revert", "probe": "probe"}.get(etype, "other"),
            text=e.get("change_summary"),
            raw_ref=f"{ev_path.name}:{lineno}",
            extra={k: e.get(k) for k in ("ip16", "request_action", "param_family",
                                         "success_observed", "time_grade", "relation_type")},
        )
