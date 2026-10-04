from datetime import datetime, timedelta, timezone

from swarmscope.evidence import verify_citation
from swarmscope.propagation import extract_units, trace
from swarmscope.schema import Actor, Event
from swarmscope.store import Store

T0 = datetime(2026, 6, 10, 12, tzinfo=timezone.utc)


def units(text):
    return {(kind, key) for kind, key, _ in extract_units(text)}


def test_extract_units_normalises_but_keeps_raw_substrings():
    text = "Use `run_probe --fast` on https://www.Example.com/a/b?x=1#top, see relay_tool.py and NO_PROXY, WikiRelay."
    found = {(k, key): raw for k, key, raw in extract_units(text)}
    assert found[("url", "example.com/a/b")] == "https://www.Example.com/a/b?x=1#top"
    assert found[("file", "relay_tool.py")] == "relay_tool.py"
    assert ("scream", "NO_PROXY") in found and ("camel", "WikiRelay") in found
    assert ("snake", "relay_tool") in found and ("code", "run_probe --fast") in found
    assert all(raw in text for raw in found.values())              # every hop stays a verbatim citation
    assert ("file", "b.html") not in units("https://x.org/a/b.html") and not units("50%2Fcounty.json done")


def make_store(tmp_path):
    store = Store(tmp_path / "t.duckdb")
    store.add_actors([Actor(actor_id=f"s:{n}", source="s", kind="agent", display_name=n.upper()) for n in "abcde"])
    rows = [  # (hours after T0, actor, text)
        (-500, "e", "old habit: see https://old.example.org/guide always"),
        (0, "a", "New trick: set BYPASS_MODE before running https://x.example.org/tool"),
        (1, "b", "Confirmed, BYPASS_MODE works"),
        (2, "c", "I also used BYPASS_MODE, docs at https://x.example.org/tool?ref=c"),
        (5, "d", "BYPASS_MODE again"),
        (6, "a", "BYPASS_MODE remains the fix"),          # origin repeating itself is not an adoption
        (400, "b", "old_guide is still on https://old.example.org/guide"),
        (401, "c", "old_guide"), (402, "d", "old_guide"),
        (700, "e", "lonely_thing_alpha"),
        (0.5, "a", "ROLLING_FIX first"), (1.5, "b", "ROLLING_FIX"), (2.5, "c", "ROLLING_FIX"),   # then never stops
        (100, "d", "ROLLING_FIX"), (150, "e", "ROLLING_FIX"), (200, "d", "ROLLING_FIX"),
        (250, "e", "ROLLING_FIX"), (300, "d", "ROLLING_FIX"), (350, "e", "ROLLING_FIX"),
    ]
    store.add_events([
        Event(event_id=f"s:msg:{i:08d}-0000-4000-8000-000000000000", source="s", ts=T0 + timedelta(hours=h),
              actor_id=f"s:{who}", channel_id=None, event_type="message", text=text, raw_ref=f"f:{i}")
        for i, (h, who, text) in enumerate(rows)])
    return store


def test_trace_finds_the_burst_and_ignores_old_or_lonely_units(tmp_path):
    store = make_store(tmp_path)
    found = {c.unit: c for c in trace(store, "s", start="2026-06-10", min_adopters=2, horizon_days=2)}
    # x.example.org/tool has a single adopter; old.example.org/guide first appeared before the window
    assert set(found) == {"BYPASS_MODE", "old_guide"}
    cascade = found["BYPASS_MODE"]
    assert cascade.origin.actor == "A" and [h.actor for h in cascade.adopters] == ["B", "C", "D"]
    assert cascade.uses_total == 5 and cascade.uses_in_horizon == 5 and cascade.burst == 1.0
    assert [h.lag_hours for h in cascade.adopters] == [1.0, 2.0, 5.0] and cascade.median_lag_hours == 2.0
    assert [h.actor for h in found["old_guide"].adopters] == ["C", "D"]      # B is the origin of old_guide
    single = [c for c in trace(store, "s", start="2026-06-10", min_adopters=1, horizon_days=2)
              if c.unit == "x.example.org/tool"]
    assert [h.actor for h in single[0].adopters] == ["C"]


def test_every_hop_is_a_citation_the_verifier_accepts(tmp_path):
    store = make_store(tmp_path)
    for cascade in trace(store, "s", start="2026-06-10", min_adopters=1, horizon_days=2):
        for hop in [cascade.origin, *cascade.adopters]:
            assert verify_citation(store, hop.event_id, hop.raw).status == "verified"


def test_burst_threshold_drops_units_that_never_stopped(tmp_path):
    store = make_store(tmp_path)
    everything = {c.unit: c for c in trace(store, "s", min_adopters=2, horizon_days=2, min_burst=0.0)}
    assert everything["ROLLING_FIX"].burst == round(3 / 9, 3)      # 3 uses inside the horizon, 6 long after
    kept = trace(store, "s", min_adopters=2, horizon_days=2, min_burst=0.5)
    assert "ROLLING_FIX" not in {c.unit for c in kept} and "BYPASS_MODE" in {c.unit for c in kept}
