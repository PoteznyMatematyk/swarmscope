from datetime import datetime, timezone

from swarmscope.evidence import verify_citation
from swarmscope.schema import Event
from swarmscope.store import Store


def make_store(tmp_path):
    store = Store(tmp_path / "t.duckdb")
    store.add_events([
        Event(event_id="e1", source="t", ts=datetime(2026, 5, 1, tzinfo=timezone.utc),
              actor_id="a", channel_id="c", event_type="message",
              text="Relay the  R5 field\nto “PHASEONE” now", raw_ref="f:1"),
        Event(event_id="e2", source="t", ts=None, actor_id=None, channel_id=None,
              event_type="probe", raw_ref="f:2"),
    ])
    return store


def test_verified_despite_whitespace_and_smart_quotes(tmp_path):
    check = verify_citation(make_store(tmp_path), "e1", 'r5 field to "PHASEONE"')
    assert check.status == "verified"


def test_hallucinated_quote_rejected(tmp_path):
    assert verify_citation(make_store(tmp_path), "e1", "R6 schedule").status == "quote_not_found"


def test_missing_event_and_empty_text(tmp_path):
    store = make_store(tmp_path)
    assert verify_citation(store, "nope", "x").status == "event_missing"
    assert verify_citation(store, "e2", "x").status == "no_text"


def test_quote_must_align_with_word_boundaries_and_have_substance(tmp_path):
    store = Store(tmp_path / "w.duckdb")
    store.add_events([Event(event_id="w1", source="t", ts=None, actor_id=None, channel_id=None, event_type="message",
                            text="another plan: do not deploy, @Opus said x_y is ready", raw_ref="f:1")])
    assert verify_citation(store, "w1", "do not deploy").status == "verified"
    assert verify_citation(store, "w1", "not deploy").status == "verified"
    assert verify_citation(store, "w1", "other plan").status == "quote_not_found"       # inside "another"
    assert verify_citation(store, "w1", "do not deplo").status == "quote_not_found"     # cut mid-word
    assert verify_citation(store, "w1", "@Opus said").status == "verified"
    assert verify_citation(store, "w1", "not").status == "quote_too_short"
    assert verify_citation(store, "w1", "is ready").status == "verified"


def test_overlong_quote_is_rejected(tmp_path):
    words = " ".join(f"word{i}" for i in range(80))
    store = Store(tmp_path / "l.duckdb")
    store.add_events([Event(event_id="l1", source="t", ts=None, actor_id=None, channel_id=None,
                            event_type="message", text=words, raw_ref="f:1")])
    assert verify_citation(store, "l1", " ".join(words.split()[:60])).status == "verified"
    assert verify_citation(store, "l1", " ".join(words.split()[:61])).status == "quote_too_long"
