"""Adapter for the AI Village dataset (https://huggingface.co/datasets/aidigestorg/ai-village).

Column names follow the dataset's SCHEMA.md (export of 2026-09-20); row counts were checked against
``manifest.json``. Mapping decisions:

* ``events`` is the timeline backbone. Talk events become ``message`` events: they are a superset of
  ``chat_messages`` (57 user messages exist only here) and carry the canonical ``event_index``. Every
  other ``actionType`` keeps its name in ``subtype``.
* The raw model ``output`` (reasoning, ~80 % of the bytes) is not copied; ``raw_ref`` points back to it.
* Values inside ``events.data`` are all strings ("37666", "false") and are converted where used.
* An event's ``text`` is its only citable surface: single-field events hold the raw text, multi-field
  events hold ``label: value`` lines, so a quote from any part still verifies.

Tables mapped (file stems, .jsonl.gz):
  agents                    -> actors (agent)          events USER_TALK -> actors (human viewers)
  chat_rooms                -> channels (chat_room)    computer_use_sessions -> channels (cu_session)
  events                    -> events: message | session | action | other
  computer_use_sessions     -> events: session / CU_SESSION
  village_goals, agent_goals-> events: goal
  agent_memories            -> events: memory          (heavy tier, when present)
  computer_use_turns        -> events: action          (heavy tier, opt-in via include_turns)
Not ingested: chat_messages (redundant with talk events, used as a cross-check), summaries (LLM-written,
secondary), claude_code_* (different tool surface, analyse separately).
"""

from __future__ import annotations

import json
from collections.abc import Iterator
from pathlib import Path

from ..schema import Actor, Channel, Event
from ._io import find, parse_ts, read_jsonl

SOURCE = "ai_village"

# actionType -> (event_type, text fields, scalar fields kept in ``extra``)
_ACTIONS: dict[str, tuple[str, tuple[str, ...], tuple[str, ...]]] = {
    "START_USING_COMPUTER": ("session", ("sessionGoal",), ("shortDisplayedSessionGoal",)),
    "STOP_USING_COMPUTER": ("session", ("summary",), ()),
    "CONSOLIDATE": ("other", ("nextSessionGoal",), ("nextShortDisplayedSessionGoal",)),
    "SEARCH_HISTORY": ("action", ("query", "answerToQuery"), ("startDay", "endDay", "startDate", "endDate")),
    "REQUEST_HUMAN_HELPER": ("action", ("sessionGoal", "humanConstraints"),
                             ("estimatedDuration", "humanUseSessionRequestId")),
    "CANCEL_REQUEST_FOR_HUMAN_HELPER": ("action", (), ()),
    "STOP_HUMAN_USE_SESSION": ("other", ("summary", "endComment"), ("endReason",)),
    "OUTREACH_APPROVAL_REQUEST": ("action", ("recipient", "medium", "rationale", "messageContent"),
                                  ("outreachApprovalRequestId",)),
    "OUTREACH_APPROVAL_RESPONSE": ("other", ("approval", "adminComment", "recipient"),
                                   ("outreachApprovalRequestId", "medium")),
    "ENTER_ROOM": ("other", ("previousRoomName", "roomName"), ("previousRoomId",)),
    "USER_NAME_CHANGE": ("other", ("oldName", "newName"), ("userId",)),
    "PAUSE": ("other", (), ("seconds",)),
    "WAIT": ("other", (), ()),
    "REQUEST_GOOGLE_SIGN_IN": ("other", (), ()),
    "RESTARTING_AFTER_GOOGLE_SIGN_IN": ("other", (), ()),
}


def _agent(value) -> str | None:
    return f"{SOURCE}:agent:{value}" if value else None


def _user(value) -> str | None:
    return f"{SOURCE}:user:{value}" if value else None


def _room(value) -> str | None:
    return f"{SOURCE}:room:{value}" if value else None


def _int(value) -> int | None:
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _bool(value) -> bool | None:
    return {"true": True, "false": False}.get(str(value).lower())


def _cut(value, limit: int) -> str | None:
    if value in (None, ""):
        return None
    s = value if isinstance(value, str) else json.dumps(value, ensure_ascii=False)
    return s if len(s) <= limit else s[:limit]


def _clean(extra: dict) -> dict:
    return {k: v for k, v in extra.items() if v not in (None, "")}


def _data(record: dict) -> dict:
    data = record.get("data")
    return json.loads(data) if isinstance(data, str) else (data or {})


def _text(d: dict, fields: tuple[str, ...]) -> str | None:
    """One field -> the raw text; several -> ``label: value`` lines so every part stays citable."""
    parts = [(f, d[f]) for f in fields if d.get(f) not in (None, "")]
    if not parts:
        return None
    return str(parts[0][1]) if len(fields) == 1 else "\n".join(f"{f}: {v}" for f, v in parts)


def actors(raw_dir: Path) -> Iterator[Actor]:
    if path := find(raw_dir, "agents.jsonl"):
        for _, a in read_jsonl(path):
            yield Actor(
                actor_id=_agent(a["id"]), source=SOURCE, kind="agent", display_name=a.get("name"),
                model=a.get("model_string"),
                extra=_clean({k: a.get(k) for k in ("created_at", "is_participating",
                                                    "input_tokens_used", "output_tokens_used")}),
            )
    # Viewers: the users table is not exported; handles only appear in USER_TALK / USER_NAME_CHANGE
    # (the latest one wins). Most renamers never chat, so name changes must be scanned too.
    if path := find(raw_dir, "events.jsonl"):
        latest: dict[str, tuple[str, str | None]] = {}
        for _, r in read_jsonl(path, contains="USER_"):
            d = _data(r)
            kind = d.get("actionType")
            if kind == "USER_TALK":
                uid, name = d.get("speakerId"), d.get("speakerName")
            elif kind == "USER_NAME_CHANGE":
                uid, name = d.get("userId"), d.get("newName")
            else:
                continue
            seen = latest.get(uid)
            if uid and (seen is None or r["created_at"] > seen[0]):
                latest[uid] = (r["created_at"], name or None)
        for uid, (_, name) in latest.items():
            yield Actor(actor_id=_user(uid), source=SOURCE, kind="human", display_name=name)


def channels(raw_dir: Path) -> Iterator[Channel]:
    if path := find(raw_dir, "chat_rooms.jsonl"):
        for _, r in read_jsonl(path):
            yield Channel(
                channel_id=f"{SOURCE}:room:{r['id']}", source=SOURCE, kind="chat_room", name=r.get("name"),
                extra=_clean({k: r.get(k) for k in ("created_at", "deleted_at",
                                                    "whitelisted_agent_names", "blacklisted_agent_names")}),
            )
    if path := find(raw_dir, "computer_use_sessions.jsonl"):
        for _, s in read_jsonl(path):
            yield Channel(
                channel_id=f"{SOURCE}:cu:{s['id']}", source=SOURCE, kind="cu_session",
                name=s.get("short_displayed_session_goal") or s.get("session_goal"),
                extra={"agent": s.get("agent_id")},
            )


def events(raw_dir: Path, include_turns: bool = False) -> Iterator[Event]:
    yield from _timeline(raw_dir)
    yield from _sessions(raw_dir)
    yield from _goals(raw_dir)
    yield from _memories(raw_dir)
    if include_turns:
        yield from _turns(raw_dir)


def _timeline(raw_dir: Path) -> Iterator[Event]:
    if not (path := find(raw_dir, "events.jsonl")):
        return
    for lineno, r in read_jsonl(path):
        d = _data(r)
        kind = d.get("actionType")
        extra = {"event_index": r.get("event_index"), "in_tokens": _int(d.get("inputTokens")),
                 "out_tokens": _int(d.get("outputTokens"))}
        common = {"source": SOURCE, "ts": parse_ts(r.get("created_at")), "subtype": kind,
                  "raw_ref": f"{path.name}:{lineno}"}

        if kind in ("AGENT_TALK", "USER_TALK"):
            human = kind == "USER_TALK"
            if human:
                extra.update(speaker_name=d.get("speakerName"), approved=_bool(d.get("hasBeenApproved")))
            yield Event(
                event_id=f"{SOURCE}:msg:{d['messageId']}",
                actor_id=_user(d.get("speakerId")) if human else _agent(d.get("speakerId")),
                channel_id=_room(d.get("roomId")), event_type="message", text=d.get("content"),
                extra=_clean(extra), **common,
            )
            continue

        event_type, text_fields, scalars = _ACTIONS.get(kind, ("other", (), ()))
        extra.update({k: d.get(k) for k in scalars})
        session, room = d.get("computerUseSessionId"), d.get("roomId")
        if session and room:
            extra["room_id"] = room
        yield Event(
            event_id=f"{SOURCE}:evt:{r['id']}",
            actor_id=_user(d.get("userId")) if kind == "USER_NAME_CHANGE" else _agent(d.get("agentId")),
            channel_id=f"{SOURCE}:cu:{session}" if session else _room(room),
            event_type=event_type, text=_text(d, text_fields), extra=_clean(extra), **common,
        )


def _sessions(raw_dir: Path) -> Iterator[Event]:
    if not (path := find(raw_dir, "computer_use_sessions.jsonl")):
        return
    for lineno, s in read_jsonl(path):
        yield Event(
            event_id=f"{SOURCE}:cus:{s['id']}", source=SOURCE, ts=parse_ts(s.get("created_at")),
            actor_id=_agent(s.get("agent_id")), channel_id=f"{SOURCE}:cu:{s['id']}",
            event_type="session", subtype="CU_SESSION", text=s.get("session_goal"),
            raw_ref=f"{path.name}:{lineno}",
            extra=_clean({"short_goal": s.get("short_displayed_session_goal"),
                          "asked_to_stop": s.get("has_been_asked_to_stop")}),
        )


def _goals(raw_dir: Path) -> Iterator[Event]:
    """Village goals carry their text in ``goal``; private agent goals in ``name`` (+ optional ``description``)."""
    for stem, scope, text_fields in (("village_goals.jsonl", "village", ("goal",)),
                                     ("agent_goals.jsonl", "agent", ("name", "description"))):
        if not (path := find(raw_dir, stem)):
            continue
        for lineno, g in read_jsonl(path):
            yield Event(
                event_id=f"{SOURCE}:goal:{scope}:{g['id']}", source=SOURCE,
                ts=parse_ts(g.get("start_time") or g.get("created_at")),
                actor_id=_agent(g.get("agent_id")), channel_id=None, event_type="goal",
                subtype=f"{scope.upper()}_GOAL",
                text="\n\n".join(str(g[f]) for f in text_fields if g.get(f)) or None,
                raw_ref=f"{path.name}:{lineno}",
                extra=_clean({"end_time": g.get("end_time"), "short_name": g.get("short_name")}),
            )


def _memories(raw_dir: Path) -> Iterator[Event]:
    if not (path := find(raw_dir, "agent_memories.jsonl")):
        return
    for lineno, m in read_jsonl(path):
        yield Event(
            event_id=f"{SOURCE}:mem:{m['id']}", source=SOURCE, ts=parse_ts(m.get("created_at")),
            actor_id=_agent(m.get("agent_id")), channel_id=None, event_type="memory", subtype="MEMORY",
            text=m.get("content"), raw_ref=f"{path.name}:{lineno}",
        )


def _action_name(action) -> str | None:
    if not isinstance(action, dict):
        return None
    return action.get("action") or ("bash" if "command" in action else None)


def _turns(raw_dir: Path) -> Iterator[Event]:
    """Turns have no agent column: the owner comes from the session table."""
    turns, sessions = find(raw_dir, "computer_use_turns.jsonl"), find(raw_dir, "computer_use_sessions.jsonl")
    if not (turns and sessions):
        return
    owner = {s["id"]: s["agent_id"] for _, s in read_jsonl(sessions)}
    for lineno, t in read_jsonl(turns):
        sid, action = t.get("session_id"), t.get("agent_action")
        yield Event(
            event_id=f"{SOURCE}:turn:{t['id']}", source=SOURCE, ts=parse_ts(t.get("created_at")),
            actor_id=_agent(owner.get(sid)), channel_id=f"{SOURCE}:cu:{sid}" if sid else None,
            event_type="action", subtype=_action_name(action),
            text=json.dumps(action, ensure_ascii=False) if action else None,
            raw_ref=f"{turns.name}:{lineno}",
            extra=_clean({"output": _cut(t.get("output"), 2000), "error": _cut(t.get("error"), 1000),
                          "redacted": t.get("screenshot_is_redacted")}),
        )
