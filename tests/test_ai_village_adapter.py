import gzip
import json

from swarmscope.adapters import ai_village
from swarmscope.evidence import verify_citation
from swarmscope.store import Store


def write(raw, name, rows):
    with gzip.open(raw / f"{name}.jsonl.gz", "wt", encoding="utf-8") as fh:
        for row in rows:
            fh.write(json.dumps(row) + "\n")


def event(index, data, created="2026-06-01 09:01:00.25"):
    return {"id": f"E{index}", "event_index": index, "created_at": created, "data": data}


def make_raw(tmp_path):
    write(tmp_path, "agents", [{"id": "A1", "name": "Claude Opus 4.8", "model_string": "claude-opus-4-8",
                                "created_at": "2026-05-28 10:00:00", "is_participating": True}])
    write(tmp_path, "chat_rooms", [{"id": "R1", "name": "general", "created_at": "2025-04-02 17:00:00",
                                    "deleted_at": None}])
    write(tmp_path, "computer_use_sessions", [{"id": "S1", "agent_id": "A1", "session_goal": "Fix the deploy",
                                               "short_displayed_session_goal": "Fix deploy",
                                               "created_at": "2026-06-01 09:00:00",
                                               "has_been_asked_to_stop": False}])
    write(tmp_path, "village_goals", [{"id": "G1", "goal": "Follow your leader!",
                                       "start_time": "2026-06-01 00:00:00", "end_time": None,
                                       "created_at": "2026-05-31 00:00:00"}])
    write(tmp_path, "agent_goals", [{"id": "AG1", "agent_id": "A1", "name": "Maximize", "short_name": "Max",
                                     "description": "Win the benchmark", "start_time": None, "end_time": None,
                                     "created_at": "2026-07-03 00:00:00"}])
    write(tmp_path, "events", [
        event(10, {"actionType": "AGENT_TALK", "messageId": "M1", "speakerId": "A1", "roomId": "R1",
                   "content": "I will relay the plan.", "inputTokens": "120", "outputTokens": "7",
                   "output": "[reasoning that must not be copied]"}),
        event(11, {"actionType": "USER_TALK", "messageId": "M2", "speakerId": "U1", "speakerName": "Viewer",
                   "roomId": "R1", "content": "Please stop.", "hasBeenApproved": "false"}),
        event(12, {"actionType": "OUTREACH_APPROVAL_REQUEST", "agentId": "A1", "recipient": "HN",
                   "medium": "Show HN", "rationale": "Free demo", "messageContent": "Title: Show HN",
                   "outreachApprovalRequestId": "OR1"}),
        event(13, {"actionType": "PAUSE", "agentId": "A1", "seconds": "300", "roomId": "R1"}),
        event(14, {"actionType": "STOP_USING_COMPUTER", "agentId": "A1", "roomId": "R1",
                   "computerUseSessionId": "S1", "summary": "Deploy fixed."}),
        event(15, {"actionType": "SOMETHING_NEW", "agentId": "A1"}),
        event(16, {"actionType": "USER_NAME_CHANGE", "userId": "U2", "oldName": "", "newName": "Lurker"},
              created="2026-06-01 09:06:00"),
    ])
    return tmp_path


def test_talk_events_become_messages_and_drop_raw_output(tmp_path):
    evs = {e.event_id: e for e in ai_village.events(make_raw(tmp_path))}
    agent_msg, user_msg = evs["ai_village:msg:M1"], evs["ai_village:msg:M2"]

    assert (agent_msg.event_type, agent_msg.subtype) == ("message", "AGENT_TALK")
    assert agent_msg.text == "I will relay the plan."
    assert agent_msg.actor_id == "ai_village:agent:A1" and agent_msg.channel_id == "ai_village:room:R1"
    assert agent_msg.ts.isoformat() == "2026-06-01T09:01:00.250000+00:00"   # zone-less input read as UTC
    assert agent_msg.extra == {"event_index": 10, "in_tokens": 120, "out_tokens": 7}
    assert agent_msg.raw_ref == "events.jsonl.gz:1"

    assert user_msg.actor_id == "ai_village:user:U1"
    assert user_msg.extra["speaker_name"] == "Viewer" and user_msg.extra["approved"] is False


def test_multi_field_text_keeps_every_part_citable(tmp_path):
    evs = list(ai_village.events(make_raw(tmp_path)))
    request = next(e for e in evs if e.subtype == "OUTREACH_APPROVAL_REQUEST")
    assert request.text == "recipient: HN\nmedium: Show HN\nrationale: Free demo\nmessageContent: Title: Show HN"
    assert request.extra["outreachApprovalRequestId"] == "OR1"

    stop = next(e for e in evs if e.subtype == "STOP_USING_COMPUTER")
    assert stop.text == "Deploy fixed."                       # single field stays raw
    assert stop.channel_id == "ai_village:cu:S1" and stop.extra["room_id"] == "R1"


def test_unknown_action_types_and_other_tables_are_kept(tmp_path):
    evs = list(ai_village.events(make_raw(tmp_path)))
    assert next(e for e in evs if e.subtype == "SOMETHING_NEW").event_type == "other"
    assert next(e for e in evs if e.subtype == "PAUSE").extra["seconds"] == "300"

    session = next(e for e in evs if e.subtype == "CU_SESSION")
    assert session.text == "Fix the deploy" and session.actor_id == "ai_village:agent:A1"
    village, personal = (next(e for e in evs if e.subtype == s) for s in ("VILLAGE_GOAL", "AGENT_GOAL"))
    assert village.text == "Follow your leader!" and village.actor_id is None
    assert personal.text == "Maximize\n\nWin the benchmark"    # goal statement lives in ``name``
    assert personal.actor_id == "ai_village:agent:A1" and personal.extra["short_name"] == "Max"
    assert personal.ts.isoformat() == "2026-07-03T00:00:00+00:00"   # falls back to created_at


def test_turns_take_their_agent_from_the_session(tmp_path):
    raw = make_raw(tmp_path)
    write(raw, "computer_use_turns", [
        {"id": "T1", "session_id": "S1", "created_at": "2026-06-01 09:02:00",
         "agent_action": {"action": "left_click", "coordinate": [1, 2]}, "output": None,
         "error": None, "screenshot_is_redacted": False},
        {"id": "T2", "session_id": "S1", "created_at": "2026-06-01 09:03:00",
         "agent_action": {"command": "ls"}, "output": "a.txt", "error": None},
        {"id": "T3", "session_id": "S1", "created_at": "2026-06-01 09:04:00", "agent_action": None},
    ])
    assert not any(e.event_id.startswith("ai_village:turn:") for e in ai_village.events(raw))
    turns = {e.event_id: e for e in ai_village.events(raw, include_turns=True)
             if e.event_id.startswith("ai_village:turn:")}
    assert turns["ai_village:turn:T1"].subtype == "left_click"
    assert turns["ai_village:turn:T1"].actor_id == "ai_village:agent:A1"
    assert turns["ai_village:turn:T2"].subtype == "bash" and turns["ai_village:turn:T2"].extra["output"] == "a.txt"
    assert turns["ai_village:turn:T3"].text is None


def test_actors_and_channels(tmp_path):
    raw = make_raw(tmp_path)
    actors = {a.actor_id: a for a in ai_village.actors(raw)}
    assert actors["ai_village:agent:A1"].kind == "agent" and actors["ai_village:agent:A1"].model == "claude-opus-4-8"
    assert actors["ai_village:user:U1"].kind == "human" and actors["ai_village:user:U1"].display_name == "Viewer"
    assert actors["ai_village:user:U2"].display_name == "Lurker"     # renamed but never chatted
    channels = {c.channel_id: c for c in ai_village.channels(raw)}
    assert channels["ai_village:room:R1"].name == "general"
    assert channels["ai_village:cu:S1"].kind == "cu_session" and channels["ai_village:cu:S1"].name == "Fix deploy"


def test_store_roundtrip_supports_citations_and_subtype_stats(tmp_path):
    raw = make_raw(tmp_path)
    store = Store(tmp_path / "t.duckdb")
    store.add_events(ai_village.events(raw))
    assert verify_citation(store, "ai_village:msg:M1", "relay the PLAN").status == "verified"
    request_id = next(e.event_id for e in ai_village.events(raw) if e.subtype == "OUTREACH_APPROVAL_REQUEST")
    assert verify_citation(store, request_id, "rationale: free demo").status == "verified"
    assert verify_citation(store, "ai_village:msg:M1", "reasoning that must not be copied").status == "quote_not_found"
    assert any(row[:4] == ("ai_village", "message", "AGENT_TALK", 1) for row in store.stats())
