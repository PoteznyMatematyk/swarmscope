"""Tests for wikiswarm.aggregate module."""
import json
from pathlib import Path
import pytest
from wikiswarm.aggregate import aggregate

ROOT = Path(__file__).resolve().parent.parent


def test_synthetic_fixture():
    fixture_path = ROOT / "gate" / "fixtures" / "synthetic_tuples.jsonl"
    expected_path = ROOT / "gate" / "fixtures" / "expected_metrics.json"

    with open(fixture_path, encoding="utf-8") as f:
        tuples = [json.loads(line) for line in f if line.strip()]

    with open(expected_path, encoding="utf-8") as f:
        expected = json.loads(f.read())

    got = aggregate(tuples)
    assert got == expected


def test_consensus_value_tie_breaking():
    # Two distinct values each with 1 signature in fh:
    # First tuple at 10:00 with value "100" (sig A)
    # Second tuple at 10:05 with value "200" (sig B)
    # Tie broken by earliest tuple -> consensus must be "100"
    tuples = [
        {
            "record_id": "r1", "wall_time": "2026-06-01T10:00:00Z", "signature": "A",
            "family": "datausa-grocery-workforce", "round": 1, "item": "GA",
            "value": "100", "kind": "answered", "used_cache": False,
            "task_clock": None, "cohort_tier": None, "corrects_value": None, "quote": "q1"
        },
        {
            "record_id": "r2", "wall_time": "2026-06-01T10:05:00Z", "signature": "B",
            "family": "datausa-grocery-workforce", "round": 1, "item": "GA",
            "value": "200", "kind": "answered", "used_cache": False,
            "task_clock": None, "cohort_tier": None, "corrects_value": None, "quote": "q2"
        },
    ]
    res = aggregate(tuples)
    assert res["n_units"] == 1
    unit = res["units"][0]
    assert unit["consensus_value"] == "100"
    assert unit["revealer"] == "A"


def test_revealer_excluded_from_receivers():
    # Revealer is A. A posts first-hand answer at 10:00.
    # B posts first-hand answer at 10:10.
    # A posts another first-hand answer at 10:20.
    # Receivers should be only B (A must be excluded).
    tuples = [
        {
            "record_id": "r1", "wall_time": "2026-06-01T10:00:00Z", "signature": "A",
            "family": "datausa-grocery-workforce", "round": 1, "item": "GA",
            "value": "100", "kind": "answered", "used_cache": False,
            "task_clock": None, "cohort_tier": None, "corrects_value": None, "quote": "q1"
        },
        {
            "record_id": "r2", "wall_time": "2026-06-01T10:10:00Z", "signature": "B",
            "family": "datausa-grocery-workforce", "round": 1, "item": "GA",
            "value": "100", "kind": "answered", "used_cache": False,
            "task_clock": None, "cohort_tier": None, "corrects_value": None, "quote": "q2"
        },
        {
            "record_id": "r3", "wall_time": "2026-06-01T10:20:00Z", "signature": "A",
            "family": "datausa-grocery-workforce", "round": 1, "item": "GA",
            "value": "100", "kind": "answered", "used_cache": False,
            "task_clock": None, "cohort_tier": None, "corrects_value": None, "quote": "q3"
        },
    ]
    res = aggregate(tuples)
    unit = res["units"][0]
    assert unit["revealer"] == "A"
    assert unit["receivers"] == 1
    assert unit["exposed"] == 1


def test_receiver_before_reveal_not_exposed():
    # Receiver B arrives before reveal:
    # B posts observed_prompt at 10:00
    # A posts reveal at 10:05
    # C posts answer at 10:10
    # Receivers = B, C (2 receivers)
    # B is NOT exposed (10:00 <= 10:05)
    # C IS exposed (10:10 > 10:05)
    tuples = [
        {
            "record_id": "r1", "wall_time": "2026-06-01T10:00:00Z", "signature": "B",
            "family": "datausa-grocery-workforce", "round": 1, "item": "GA",
            "value": None, "kind": "observed_prompt", "used_cache": False,
            "task_clock": None, "cohort_tier": None, "corrects_value": None, "quote": "q1"
        },
        {
            "record_id": "r2", "wall_time": "2026-06-01T10:05:00Z", "signature": "A",
            "family": "datausa-grocery-workforce", "round": 1, "item": "GA",
            "value": "100", "kind": "answered", "used_cache": False,
            "task_clock": None, "cohort_tier": None, "corrects_value": None, "quote": "q2"
        },
        {
            "record_id": "r3", "wall_time": "2026-06-01T10:10:00Z", "signature": "C",
            "family": "datausa-grocery-workforce", "round": 1, "item": "GA",
            "value": "100", "kind": "answered", "used_cache": False,
            "task_clock": None, "cohort_tier": None, "corrects_value": None, "quote": "q3"
        },
    ]
    res = aggregate(tuples)
    unit = res["units"][0]
    assert unit["revealer"] == "A"
    assert unit["receivers"] == 2
    assert unit["exposed"] == 1


def test_null_round_assigned_and_dropped():
    # Form unit (datausa-grocery-workforce, 1, GA) with A and B
    # Form unit (datausa-grocery-workforce, 2, FL) with A and B
    # Null round 1: item "GA" matches unit 1 uniquely -> assigned to round 1
    # Null round 2: item "TX" matches no unit -> dropped
    # Null round 3: form two units with same item (e.g. datausa-grocery-workforce, 1, CA and 2, CA) -> dropped
    tuples = [
        {
            "record_id": "r1", "wall_time": "2026-06-01T10:00:00Z", "signature": "A",
            "family": "datausa-grocery-workforce", "round": 1, "item": "GA",
            "value": "100", "kind": "answered", "used_cache": False,
            "task_clock": None, "cohort_tier": None, "corrects_value": None, "quote": "q1"
        },
        {
            "record_id": "r2", "wall_time": "2026-06-01T10:05:00Z", "signature": "B",
            "family": "datausa-grocery-workforce", "round": 1, "item": "GA",
            "value": "100", "kind": "answered", "used_cache": False,
            "task_clock": None, "cohort_tier": None, "corrects_value": None, "quote": "q2"
        },
        {
            "record_id": "r3", "wall_time": "2026-06-01T10:10:00Z", "signature": "A",
            "family": "datausa-grocery-workforce", "round": 1, "item": "CA",
            "value": "200", "kind": "answered", "used_cache": False,
            "task_clock": None, "cohort_tier": None, "corrects_value": None, "quote": "q3"
        },
        {
            "record_id": "r4", "wall_time": "2026-06-01T10:15:00Z", "signature": "B",
            "family": "datausa-grocery-workforce", "round": 1, "item": "CA",
            "value": "200", "kind": "answered", "used_cache": False,
            "task_clock": None, "cohort_tier": None, "corrects_value": None, "quote": "q4"
        },
        {
            "record_id": "r5", "wall_time": "2026-06-01T10:20:00Z", "signature": "A",
            "family": "datausa-grocery-workforce", "round": 2, "item": "CA",
            "value": "300", "kind": "answered", "used_cache": False,
            "task_clock": None, "cohort_tier": None, "corrects_value": None, "quote": "q5"
        },
        {
            "record_id": "r6", "wall_time": "2026-06-01T10:25:00Z", "signature": "B",
            "family": "datausa-grocery-workforce", "round": 2, "item": "CA",
            "value": "300", "kind": "answered", "used_cache": False,
            "task_clock": None, "cohort_tier": None, "corrects_value": None, "quote": "q6"
        },
        # Null round tuple 1: GA (unique match -> round 1)
        {
            "record_id": "r7", "wall_time": "2026-06-01T10:30:00Z", "signature": "C",
            "family": "datausa-grocery-workforce", "round": None, "item": "Georgia",
            "value": "100", "kind": "answered", "used_cache": False,
            "task_clock": None, "cohort_tier": None, "corrects_value": None, "quote": "q7"
        },
        # Null round tuple 2: TX (no unit matches -> dropped)
        {
            "record_id": "r8", "wall_time": "2026-06-01T10:35:00Z", "signature": "D",
            "family": "datausa-grocery-workforce", "round": None, "item": "Texas",
            "value": "400", "kind": "answered", "used_cache": False,
            "task_clock": None, "cohort_tier": None, "corrects_value": None, "quote": "q8"
        },
        # Null round tuple 3: CA (matches two units: round 1 and round 2 -> dropped)
        {
            "record_id": "r9", "wall_time": "2026-06-01T10:40:00Z", "signature": "E",
            "family": "datausa-grocery-workforce", "round": None, "item": "California",
            "value": "200", "kind": "answered", "used_cache": False,
            "task_clock": None, "cohort_tier": None, "corrects_value": None, "quote": "q9"
        },
    ]
    res = aggregate(tuples)
    assert res["null_round_dropped"] == 2
    ga_unit = [u for u in res["units"] if u["item"] == "GA"][0]
    assert ga_unit["receivers"] == 2  # B and C
