from dataclasses import asdict
from datetime import datetime, timezone

from swarmscope.propagation import trace
from swarmscope.report import build_report, locate
from swarmscope.schema import Actor, Channel, Event
from swarmscope.store import Store

DAY_MAP = {"2026-06-10": 435, "2026-06-11": 436}
U1, U2 = "cccccccc-1111-4111-8111-111111111111", "dddddddd-2222-4222-8222-222222222222"


def make_store(tmp_path):
    store = Store(tmp_path / "t.duckdb")
    store.add_actors([Actor(actor_id=f"s:agent:{n}", source="s", kind="agent", display_name=n.upper()) for n in "ab"])
    store.add_channels([Channel(channel_id="s:room:1", source="s", kind="chat_room", name="general")])
    store.add_events([
        Event(event_id=f"s:msg:{U1}", source="s", ts=datetime(2026, 6, 10, 20, tzinfo=timezone.utc),
              actor_id="s:agent:a", channel_id="s:room:1", event_type="message", subtype="AGENT_TALK",
              text="Kick-off.\nUse “WIRE_FIX” before shipping.", raw_ref="f:1"),
        Event(event_id=f"s:msg:{U2}", source="s", ts=datetime(2026, 6, 10, 21, tzinfo=timezone.utc),
              actor_id="s:agent:b", channel_id="s:room:1", event_type="message", subtype="AGENT_TALK",
              text="WIRE_FIX confirmed", raw_ref="f:2"),
    ])
    return store


def test_locate_ignores_whitespace_and_quote_style():
    text = "Kick-off.\nUse “WIRE_FIX”  before shipping."
    start, end = locate(text, 'use "WIRE_FIX" before')
    assert text[start:end] == "Use “WIRE_FIX”  before"
    assert locate(text, "not there") is None


def test_report_reverifies_enriches_and_counts(tmp_path):
    store = make_store(tmp_path)
    batch = {"model": "m1", "lens": "structure", "claims": [
        {"id": "Q3-1", "question": "Q3", "claim": "WIRE_FIX spread", "actors": ["A", "B"],
         "evidence": [{"ref": "cccccccc11", "quote": "Use “WIRE_FIX” before"}, {"ref": "dddddddd22", "quote": "WIRE_FIX confirmed"}]},
        {"id": "Q3-2", "question": "Q3", "claim": "invented", "evidence": [{"ref": "cccccccc11", "quote": "made up words"}]},
    ]}
    repaired = {**batch, "claims": batch["claims"][:1]}
    report = build_report(
        store, meta={"title": "t"}, batches=[repaired], first_pass=[batch], day_map=DAY_MAP,
        findings=[{"id": "F1", "title": "x", "evidence": [{"ref": "dddddddd22", "quote": "WIRE_FIX confirmed", "role": "adoption"}],
                   "counter_evidence": [{"ref": "dddddddd22", "quote": "nowhere"}]}],
        cascades=[asdict(c) for c in trace(store, "s", min_adopters=1, horizon_days=2)])

    ev = report["claims"][0]["evidence"][0]
    assert ev["status"] == "verified" and ev["actor"] == "A" and ev["room"] == "general"
    assert ev["context"][ev["span"][0]:ev["span"][1]] == "Use “WIRE_FIX” before"
    assert ev["deeplink"].startswith("https://theaidigest.org/village?day=435&time=")
    assert report["metrics"]["first_pass"]["quote_reject_rate"] == round(1 / 3, 4)      # one of three quotes invented
    assert report["metrics"]["final"]["quote_reject_rate"] == 0.0
    assert report["metrics"]["first_pass_by_model"]["m1"]["quotes"] == 3
    finding = report["findings"][0]
    assert finding["evidence"][0]["role"] == "adoption" and finding["all_verified"] is False   # counter-evidence failed
    assert report["metrics"]["tracer"] == {"hops": 2, "hops_rejected": 0}
    assert report["cascades"][0]["adopters"][0]["deeplink"].startswith("https://theaidigest.org/village?day=435")
