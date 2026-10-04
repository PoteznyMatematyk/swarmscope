"""Foreknowledge must need two posts of the same signature in the right order, and credit the swarm only
when another signature mentioned the item first."""
from wikiswarm.foreknowledge import compute

F = "datausa-grocery-workforce"
UNITS = [{"family": F, "round": 3, "item": "NV", "consensus_value": "20369"}]


def t(rid, time, sig, kind, item="Nevada", value="20,369", rnd=3):
    return {"record_id": rid, "wall_time": f"2026-06-16T{time}:00Z", "signature": sig, "family": F,
            "round": rnd, "item": item, "value": value, "kind": kind, "used_cache": False, "quote": f"q{rid}"}


def test_ahead_after_other_with_value():
    rows = [t("a", "10:00", "A", "answered"), t("b", "10:10", "B", "predicted"), t("c", "10:30", "B", "answered")]
    tot = compute(rows, UNITS)["totals"]
    assert (tot["item_ahead"], tot["value_ahead"], tot["item_ahead_after_other"]) == (1, 1, 1)


def test_same_post_is_not_foreknowledge():
    rows = [t("a", "10:00", "A", "answered"), t("c", "10:30", "B", "predicted"), t("c", "10:30", "B", "answered")]
    assert compute(rows, UNITS)["totals"]["item_ahead"] == 0


def test_prediction_without_value_and_before_anyone_else():
    rows = [t("b", "09:00", "B", "predicted", value=None), t("a", "10:00", "A", "answered"),
            t("c", "10:30", "B", "observed_prompt", value=None)]
    tot = compute(rows, UNITS)["totals"]
    assert (tot["item_ahead"], tot["value_ahead"], tot["item_ahead_after_other"]) == (1, 0, 0)
