"""Tests for wikiswarm.figures module."""
import json
import tempfile
from pathlib import Path
import pytest

from wikiswarm.aggregate import aggregate
from wikiswarm.figures import generate_all

ROOT = Path(__file__).resolve().parent.parent


def test_figures_on_fixture():
    fixture_tuples = ROOT / "gate" / "fixtures" / "synthetic_tuples.jsonl"
    with open(fixture_tuples, encoding="utf-8") as f:
        tuples = [json.loads(line) for line in f if line.strip()]

    metrics = aggregate(tuples)

    with tempfile.TemporaryDirectory() as td:
        tdp = Path(td)
        metrics_path = tdp / "metrics.json"
        metrics_path.write_text(json.dumps(metrics), encoding="utf-8")

        figures_dir = tdp / "figures"
        evidence_dir = tdp / "evidence"

        manifest = generate_all(
            metrics_path=metrics_path,
            tuples_path=fixture_tuples,
            figures_dir=figures_dir,
            evidence_dir=evidence_dir,
        )

        # 1. Figures exist and are non-empty
        f1 = figures_dir / "reveal_vs_receivers.svg"
        f2 = figures_dir / "lead_minutes.svg"
        f3 = figures_dir / "wrong_predictions.svg"
        ev = evidence_dir / "units.jsonl"
        mf = figures_dir / "manifest.json"

        assert f1.exists() and f1.stat().st_size > 0
        assert f2.exists() and f2.stat().st_size > 0
        assert f3.exists() and f3.stat().st_size > 0
        assert ev.exists() and ev.stat().st_size > 0
        assert mf.exists() and mf.stat().st_size > 0

        # 2. Every manifest number equals the metrics value it cites
        manifest_data = json.loads(mf.read_text(encoding="utf-8"))
        for key, val in manifest_data.items():
            assert key in metrics, f"Manifest key {key} not found in metrics"
            assert metrics[key] == val, f"Manifest value for {key} ({val}) != metrics value ({metrics[key]})"

        # 3. Check evidence rows schema
        ev_rows = [json.loads(line) for line in ev.read_text(encoding="utf-8").splitlines() if line.strip()]
        assert len(ev_rows) == metrics["n_units"]
        for er in ev_rows:
            assert "family" in er and "round" in er and "item" in er
            assert "reveal" in er and "receivers" in er
            if er["reveal"] is not None:
                assert "record_id" in er["reveal"] and "wall_time" in er["reveal"]
                assert "quote" in er["reveal"]


def test_figures_evidence_null_consensus(tmp_path):
    # Tests that when a unit has no consensus value (e.g. only observed_prompt with null value),
    # reveal in evidence/units.jsonl is None, not a bogus dict.
    from wikiswarm.aggregate import aggregate
    from wikiswarm.figures import generate_all

    tuples = [
        {
            "record_id": "r1", "wall_time": "2026-06-01T10:00:00Z", "signature": "A",
            "family": "datausa-sector61-state", "round": 1, "item": "MA",
            "value": None, "kind": "observed_prompt", "used_cache": False,
            "task_clock": "10:00:00", "cohort_tier": None, "corrects_value": None, "quote": "q1 MA 10:00:00"
        },
        {
            "record_id": "r2", "wall_time": "2026-06-01T10:05:00Z", "signature": "B",
            "family": "datausa-sector61-state", "round": 1, "item": "MA",
            "value": None, "kind": "observed_prompt", "used_cache": False,
            "task_clock": "10:05:00", "cohort_tier": None, "corrects_value": None, "quote": "q2 MA 10:05:00"
        },
    ]

    metrics = aggregate(tuples)
    assert metrics["units"][0]["consensus_value"] is None

    metrics_path = tmp_path / "metrics.json"
    metrics_path.write_text(json.dumps(metrics), encoding="utf-8")
    tuples_path = tmp_path / "tuples.jsonl"
    tuples_path.write_text("\n".join(json.dumps(t) for t in tuples) + "\n", encoding="utf-8")

    figures_dir = tmp_path / "figures"
    evidence_dir = tmp_path / "evidence"

    generate_all(metrics_path, tuples_path, figures_dir, evidence_dir)

    ev_rows = [json.loads(line) for line in (evidence_dir / "units.jsonl").read_text(encoding="utf-8").splitlines() if line.strip()]
    assert len(ev_rows) == 1
    assert ev_rows[0]["reveal"] is None
    assert len(ev_rows[0]["receivers"]) == 2  # A and B

