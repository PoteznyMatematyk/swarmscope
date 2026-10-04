from datetime import datetime, timezone

from swarmscope.claims import verify_claims
from swarmscope.evidence import ref_of, verify_citation
from swarmscope.export import export_window
from swarmscope.schema import Actor, Channel, Event
from swarmscope.store import Store

UUID1 = "aaaaaaaa-1111-4111-8111-111111111111"
UUID2 = "aaaaaaaa-2222-4222-8222-222222222222"   # shares its first 8 hex chars with UUID1
UUID3 = "bbbbbbbb-3333-4333-8333-333333333333"


def make_store(tmp_path):
    store = Store(tmp_path / "t.duckdb")
    day = lambda h: datetime(2026, 6, 1, h, tzinfo=timezone.utc)
    store.add_actors([Actor(actor_id="s:agent:1", source="s", kind="agent", display_name="Opus")])
    store.add_channels([Channel(channel_id="s:room:1", source="s", kind="chat_room", name="rest")])
    store.add_events([
        Event(event_id=f"s:msg:{UUID1}", source="s", ts=day(9), actor_id="s:agent:1", channel_id="s:room:1",
              event_type="message", subtype="AGENT_TALK", text="line one\nline two: ship it", raw_ref="f:1"),
        Event(event_id=f"s:msg:{UUID2}", source="s", ts=day(10), actor_id="s:agent:1", channel_id="s:room:1",
              event_type="message", subtype="AGENT_TALK", text="second message", raw_ref="f:2"),
        Event(event_id=f"s:evt:{UUID3}", source="s", ts=day(11), actor_id="s:agent:1", channel_id=None,
              event_type="action", subtype="SEARCH_HISTORY", text="query: x", raw_ref="f:3"),
    ])
    return store


def test_short_ref_resolves_and_ambiguity_is_rejected(tmp_path):
    store = make_store(tmp_path)
    check = verify_citation(store, ref_of(f"s:msg:{UUID3}"), "query: x")
    assert check.status == "verified" and check.event_id == f"s:evt:{UUID3}"
    assert ref_of(f"s:msg:{UUID3}") == "bbbbbbbb33"                                   # hyphens dropped
    assert verify_citation(store, "aaaaaaaa", "second message").status == "ambiguous_ref"     # shared 8-char prefix
    assert verify_citation(store, "aaaaaaaa2", "second message").status == "verified"         # longer prefix disambiguates
    assert verify_citation(store, "aaaaaaaa-2222", "second message").status == "verified"     # hyphens tolerated
    assert verify_citation(store, "aaaaaaa", "second message").status == "event_missing"      # too short to be a ref
    assert verify_citation(store, "cccccccc00", "second message").status == "event_missing"
    assert verify_citation(store, ref_of(f"s:msg:{UUID2}"), "  ").status == "empty_quote"


def test_quote_may_span_the_flattened_line_break(tmp_path):
    store = make_store(tmp_path)
    assert verify_citation(store, ref_of(f"s:msg:{UUID1}"), "line one ⏎ line two").status == "verified"
    assert verify_citation(store, ref_of(f"s:msg:{UUID1}"), "line one line two").status == "verified"
    assert verify_citation(store, ref_of(f"s:msg:{UUID1}"), "line one; line two").status == "quote_not_found"


def test_export_window_is_filtered_and_citable(tmp_path):
    store = make_store(tmp_path)
    lines = list(export_window(store, "s", "2026-06-01", "2026-06-02"))
    assert lines[0].endswith("| 2 events")                   # talk only by default
    assert lines[2] == "[06-01 09:00:00] #rest Opus {aaaaaaaa11}: line one ⏎ line two: ship it"
    everything = list(export_window(store, "s", "2026-06-01", "2026-06-02", subtypes=None))
    assert everything[-1] == "[06-01 11:00:00] Opus <SEARCH_HISTORY> {bbbbbbbb33}: query: x"
    assert len(list(export_window(store, "s", "2026-06-01", "2026-06-02", rooms=["nope"]))) == 2
    cut = list(export_window(store, "s", "2026-06-01", "2026-06-02", max_chars=4))[2]
    assert cut.endswith("line…[+24 chars]")


def test_verify_claims_statuses_and_summary(tmp_path):
    store = make_store(tmp_path)
    ref = ref_of(f"s:msg:{UUID1}")
    result = verify_claims(store, {"model": "m", "question": "q1", "claims": [
        {"id": "ok", "claim": "shipped", "evidence": [{"ref": ref, "quote": "two: ship it"}]},
        {"id": "mixed", "claim": "x", "evidence": [{"ref": ref, "quote": "two: ship it"}, {"ref": ref, "quote": "made up words"}]},
        {"id": "bad", "claim": "y", "evidence": [{"ref": "deadbeef00", "quote": "z"}]},
        {"id": "none", "claim": "z", "evidence": []},
    ]})
    status = {c["id"]: c["status"] for c in result["batches"][0]["claims"]}
    assert status == {"ok": "verified", "mixed": "partial", "bad": "rejected", "none": "no_evidence"}
    assert result["summary"]["quotes"] == 4 and result["summary"]["quote_reject_rate"] == 0.5
    first = result["batches"][0]["claims"][0]["evidence"][0]
    assert first["actor"] == "Opus" and first["room"] == "rest" and first["event_id"] == f"s:msg:{UUID1}"


def test_counted_claims_must_itemise_every_instance(tmp_path):
    store = make_store(tmp_path)
    one, two = ref_of(f"s:msg:{UUID1}"), ref_of(f"s:msg:{UUID2}")
    ev = lambda ref, quote: {"ref": ref, "quote": quote}
    result = verify_claims(store, {"claims": [
        {"id": "ok", "claim": "said twice", "count": 2, "evidence": [ev(one, "two: ship it"), ev(two, "second message")]},
        {"id": "short", "claim": "said three times", "count": 3, "evidence": [ev(one, "two: ship it"), ev(two, "second message")]},
        {"id": "same", "claim": "said twice", "count": 2, "evidence": [ev(one, "two: ship it"), ev(one, "line one")]},
        {"id": "big", "claim": "said 40 times", "count": 40, "evidence": [ev(one, "two: ship it")]},
    ]})
    assert {c["id"]: c["status"] for c in result["batches"][0]["claims"]} == {
        "ok": "verified", "short": "count_mismatch", "same": "count_mismatch", "big": "verified"}


def test_outreach_decisions_are_labelled_and_matchable(tmp_path):
    store = Store(tmp_path / "o.duckdb")
    day = lambda h: datetime(2026, 6, 1, h, tzinfo=timezone.utc)
    store.add_actors([Actor(actor_id="s:agent:1", source="s", kind="agent", display_name="GPT-5.4")])
    store.add_events([
        Event(event_id=f"s:evt:{UUID1}", source="s", ts=day(9), actor_id="s:agent:1", channel_id=None, event_type="action",
              subtype="OUTREACH_APPROVAL_REQUEST", text="recipient: HN", raw_ref="f:1", extra={"outreachApprovalRequestId": "REQ12345-aaaa"}),
        Event(event_id=f"s:evt:{UUID2}", source="s", ts=day(10), actor_id="s:agent:1", channel_id=None, event_type="other",
              subtype="OUTREACH_APPROVAL_RESPONSE", text="approval: False", raw_ref="f:2", extra={"outreachApprovalRequestId": "REQ12345-aaaa"}),
    ])
    lines = list(export_window(store, "s", "2026-06-01", "2026-06-02", subtypes=None))
    assert lines[2] == "[06-01 09:00:00] GPT-5.4 <OUTREACH_APPROVAL_REQUEST req=REQ12345> {aaaaaaaa11}: recipient: HN"
    assert lines[3].startswith("[06-01 10:00:00] ADMIN-DECISION->GPT-5.4 <OUTREACH_APPROVAL_RESPONSE req=REQ12345>")


def test_attribution_flags_and_derived_span(tmp_path):
    store = make_store(tmp_path)
    ref = ref_of(f"s:msg:{UUID1}")
    result = verify_claims(store, {"claims": [
        {"id": "ok", "claim": "Opus proposed shipping", "actors": ["Opus"], "evidence": [{"ref": ref, "quote": "two: ship it"}]},
        {"id": "ghost", "claim": "Kimi agreed", "actors": ["Opus", "Claude Kimi K2.6"], "evidence": [{"ref": ref, "quote": "two: ship it"}]},
    ]})
    by_id = {c["id"]: c for c in result["batches"][0]["claims"]}
    assert by_id["ok"]["flags"] == {} and by_id["ok"]["derived"]["first_ts"].startswith("2026-06-01T09:00")
    assert by_id["ghost"]["flags"] == {"actors_unsupported": ["Claude Kimi K2.6"]}
    assert result["summary"]["claims_flagged"] == 1 and result["summary"]["claims"] == 2
    assert all("_text" not in e for c in by_id.values() for e in c["evidence"])
