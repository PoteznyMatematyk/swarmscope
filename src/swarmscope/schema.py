"""Unified schema shared by every data source.

Every adapter maps its raw records onto three tables:

- ``events``   one row per observable thing an actor did (message, edit, tool call, ...)
- ``actors``   one row per agent / human / unknown identity
- ``channels`` one row per place events happen in (chat room, wiki page, session, ...)

``raw_ref`` always points back to the exact source record (``file:line`` or a
source-native id) so that every claim the tool makes can be traced to raw data.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, Field

EventType = Literal[
    "message",      # chat message / forum post
    "edit",         # saved revision of a shared document (wiki page, file)
    "deletion",     # document removed
    "revert",
    "probe",        # request/attempt observed in server logs without a saved body
    "action",       # computer-use / tool action
    "session",      # start of a work session (goal-bearing)
    "memory",       # agent-written long-term memory
    "goal",         # goal assignment (village-wide or per agent)
    "other",
]

ActorKind = Literal["agent", "human", "unknown"]


class Event(BaseModel):
    event_id: str
    source: str
    ts: datetime | None
    ts_uncertainty_s: float | None = None
    actor_id: str | None
    channel_id: str | None
    event_type: EventType
    subtype: str | None = None            # source-native discriminator (e.g. AI Village actionType)
    text: str | None = None
    parent_id: str | None = None          # reply-to / previous revision
    refs: list[str] = Field(default_factory=list)  # ids of events/channels this one references
    raw_ref: str                          # pointer to the raw record
    extra: dict[str, Any] = Field(default_factory=dict)


class Actor(BaseModel):
    actor_id: str
    source: str
    kind: ActorKind
    display_name: str | None = None
    model: str | None = None
    extra: dict[str, Any] = Field(default_factory=dict)


class Channel(BaseModel):
    channel_id: str
    source: str
    kind: str                              # "wiki_page", "chat_room", "cu_session", ...
    name: str | None = None
    extra: dict[str, Any] = Field(default_factory=dict)


DDL = """
CREATE TABLE IF NOT EXISTS events (
    event_id          VARCHAR PRIMARY KEY,
    source            VARCHAR NOT NULL,
    ts                TIMESTAMPTZ,
    ts_uncertainty_s  DOUBLE,
    actor_id          VARCHAR,
    channel_id        VARCHAR,
    event_type        VARCHAR NOT NULL,
    subtype           VARCHAR,
    text              VARCHAR,
    parent_id         VARCHAR,
    refs              VARCHAR[],
    raw_ref           VARCHAR NOT NULL,
    extra             JSON
);
CREATE TABLE IF NOT EXISTS actors (
    actor_id      VARCHAR PRIMARY KEY,
    source        VARCHAR NOT NULL,
    kind          VARCHAR NOT NULL,
    display_name  VARCHAR,
    model         VARCHAR,
    extra         JSON
);
CREATE TABLE IF NOT EXISTS channels (
    channel_id  VARCHAR PRIMARY KEY,
    source      VARCHAR NOT NULL,
    kind        VARCHAR NOT NULL,
    name        VARCHAR,
    extra       JSON
);
"""
