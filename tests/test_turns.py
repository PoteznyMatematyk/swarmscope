"""Layer C: slim ingest of turns/memories and citation of turns (tiny synthetic fixtures)."""

import gzip
import json

import pytest

from swarmscope.turns import actions, ingest_turns, memories, open_turns, verify_turn_quote

A1, A2 = "aaaaaaaa-0000-0000-0000-000000000001", "aaaaaaaa-0000-0000-0000-000000000002"
S1 = "bbbbbbbb-0000-0000-0000-000000000001"
T = [f"c{i}cccccc-0000-0000-0000-000000000000" for i in range(1, 6)]  # handles differ inside the first 10 hex characters


def _gz(path, rows):
    with gzip.open(path, "wt", encoding="utf-8") as f:
        for r in rows:
            f.write(json.dumps(r) + "\n")


@pytest.fixture()
def turns_db(tmp_path):
    raw = tmp_path / "raw"
    raw.mkdir()
    _gz(raw / "agents.jsonl.gz", [{"id": A1, "name": "Claude Opus 4.7", "model_string": "m1"}, {"id": A2, "name": "GPT-5.5", "model_string": "m2"}])
    _gz(raw / "computer_use_sessions.jsonl.gz", [{"id": S1, "agent_id": A1, "session_goal": "ship v8", "created_at": "2026-06-01 10:00:00.000000"}])
    _gz(raw / "computer_use_turns.jsonl.gz", [
        {"id": T[0], "session_id": S1, "agent_action": {"command": "python train.py --checkpoint v8"}, "output": "saved checkpoint v8 to disk",
         "error": None, "agent_messages": [{"thinking": "x" * 5000}], "created_at": "2026-06-01 10:05:00.000000"},
        {"id": T[1], "session_id": S1, "agent_action": {"action": "type", "text": "email sent to the admin about v8"}, "output": None,
         "error": None, "agent_messages": [], "created_at": "2026-06-01 10:06:00.000000"},
        {"id": T[2], "session_id": S1, "agent_action": None, "output": None, "error": None, "agent_messages": [], "created_at": "2026-06-01 10:07:00.000000"},
        {"id": T[3], "session_id": S1, "agent_action": {"action": "left_click", "coordinate": [1, 2]}, "output": None, "error": "timeout",
         "agent_messages": [], "created_at": "2026-06-01 13:00:00.000000"},
        {"id": T[4], "session_id": S1, "agent_action": {"command": "python -m pytest -q"}, "output": "." * 900 + "\n12 passed, 1 failed in 3.21s",
         "error": None, "agent_messages": [], "created_at": "2026-06-02 09:00:00.000000"},
    ])
    _gz(raw / "agent_memories.jsonl.gz", [{"id": "dddddddd-0000-0000-0000-000000000001", "content": "Checkpoint v8 finished and was reported.", "agent_id": A2,
                                            "created_at": "2026-06-01 11:00:00.000000"}])
    out = tmp_path / "turns.duckdb"
    stats = ingest_turns(raw, out)
    return out, stats


def test_ingest_counts_and_slim_projection(turns_db):
    out, stats = turns_db
    assert (stats["agents"], stats["sessions"], stats["turns"], stats["turns_with_action"], stats["memories"]) == (2, 1, 5, 4, 1)
    con = open_turns(out)
    cols = {r[0] for r in con.execute("DESCRIBE turns").fetchall()}
    assert "agent_messages" not in cols and {"ref", "agent", "action_type", "action_text", "out_text"} <= cols


def test_actions_window_agent_type_and_grep(turns_db):
    con = open_turns(turns_db[0])
    lines = actions(con, "opus", "2026-06-01T10:00", "2026-06-01T12:00")
    assert len(lines) == 2 and "bash: python train.py" in lines[0] and "out: saved checkpoint v8" in lines[0]  # talk-only turn skipped
    assert len(actions(con, "opus", "2026-06-01T10:00", "2026-06-01T12:00", types=["type"])) == 1
    assert len(actions(con, "opus", "2026-06-01T10:00", "2026-06-01T12:00", grep="ADMIN")) == 1
    assert actions(con, "gpt", "2026-06-01T10:00", "2026-06-01T12:00") == []  # other agent has no turns
    assert len(actions(con, "opus", "2026-06-01T12:00", "2026-06-02")) == 1  # window is [start, end) in UTC


def test_memories(turns_db):
    con = open_turns(turns_db[0])
    (line,) = memories(con, "gpt-5.5", "2026-06-01", "2026-06-02", grep="checkpoint")
    assert "Checkpoint v8 finished" in line and memories(con, "opus", "2026-06-01", "2026-06-02") == []


def test_report_merges_did_evidence_and_rejects_forged_turn_quote(tmp_path, turns_db):
    from datetime import datetime, timezone

    from swarmscope.report import build_report
    from swarmscope.schema import Actor, Channel, Event
    from swarmscope.store import Store

    store = Store(tmp_path / "t.duckdb")
    store.add_actors([Actor(actor_id="s:agent:a", source="s", kind="agent", display_name="A")])
    store.add_channels([Channel(channel_id="s:room:1", source="s", kind="chat_room", name="general")])
    store.add_events([Event(event_id="s:msg:eeeeeeee-1111-4111-8111-111111111111", source="s", ts=datetime(2026, 6, 1, 10, tzinfo=timezone.utc),
                            actor_id="s:agent:a", channel_id="s:room:1", event_type="message", subtype="AGENT_TALK",
                            text="I saved checkpoint v8 and reported it.", raw_ref="f:1")])
    ref = T[0].replace("-", "")[:10]
    finding = {"id": "F1", "title": "said vs did", "evidence": [{"ref": "eeeeeeee11", "quote": "I saved checkpoint v8 and reported it", "role": "origin"}],
               "did_evidence": [{"ref": ref, "quote": "saved checkpoint v8 to disk"}, {"ref": ref, "quote": "the deploy was fully successful"}]}
    # the village day changes at ~17:00 UTC, so 10:05 UTC on 06-01 belongs to the day that started on 05-31
    report = build_report(store, meta={"title": "t"}, findings=[finding], day_map={"2026-05-31": 99, "2026-06-01": 100}, turns=open_turns(turns_db[0]))
    ev = report["findings"][0]["evidence"]
    assert [e["status"] for e in ev] == ["verified", "verified", "quote_not_found"]
    did = ev[1]
    assert did["role"] == "did" and did["actor"] == "Claude Opus 4.7" and did["room"] == "computer-use" and did["subtype"] == "bash"
    assert did["context"][did["span"][0]:did["span"][1]] == "saved checkpoint v8 to disk" and did["deeplink"].startswith("https://theaidigest.org/village?day=99&time=")
    assert report["findings"][0]["all_verified"] is False      # the forged turn quote fails the whole finding


def test_cite_turn_deterministic(turns_db):
    con = open_turns(turns_db[0])
    ref = T[0].replace("-", "")[:10]
    assert verify_turn_quote(con, ref, "saved checkpoint v8 to disk") == "verified"      # from the output
    assert verify_turn_quote(con, ref, "python train.py --checkpoint v8") == "verified"   # from the action
    assert verify_turn_quote(con, ref, "the deploy was fully successful") == "quote_not_found"
    assert verify_turn_quote(con, ref, "ok") == "quote_too_short"
    assert verify_turn_quote(con, "ffffffffff", "saved checkpoint v8") == "event_missing"
    long_ref = T[4].replace("-", "")[:10]  # the summary line sits beyond the first 600 output characters
    assert verify_turn_quote(con, long_ref, "12 passed, 1 failed in 3.21s") == "verified"
    assert any("out-end: " in line and "1 failed" in line for line in actions(con, "opus", "2026-06-02", "2026-06-03"))
