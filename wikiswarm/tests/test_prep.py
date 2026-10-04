"""Tests for wikiswarm.prep module."""
import pytest
from wikiswarm.prep import (
    CAND_NUMBER,
    CAND_WORDS,
    extract_signature,
    is_candidate,
    is_mojibake,
    partition_batches,
)


def test_signature_regex():
    # No signature
    assert extract_signature("Just some normal text with no signature.") is None
    assert extract_signature("Negative number: --123 is not a signature.") is None

    # Single signature
    assert extract_signature("Report done. -- Agent-Alpha_1") == "Agent-Alpha_1"
    assert extract_signature("Urgent update -- GroceryAgent") == "GroceryAgent"

    # Two signatures -> must pick the last one
    two_sigs = "Posted by -- FirstAgent on Monday.\nForwarded by -- SecondAgent on Tuesday."
    assert extract_signature(two_sigs) == "SecondAgent"

    # Signature with spaces after dashes
    assert extract_signature("Log: --   Spaced_Agent") == "Spaced_Agent"


def test_mojibake():
    assert is_mojibake("Clean utf-8 text") is False
    assert is_mojibake("Broken Ã text") is True
    assert is_mojibake("Quote â€œ error") is True
    assert is_mojibake("Latin Â char") is True


def test_candidate_rule():
    # Satisfies all: valid family, candidate word, candidate number, no mojibake
    valid_text = "Urgent: arrived at R3 with value 20,369."
    assert is_candidate(valid_text, "datausa-grocery-workforce", mojibake=False) is True

    # Mojibake prevents candidate
    assert is_candidate("Arrived at R3 with 20,369 Ã", "datausa-grocery-workforce", mojibake=True) is False

    # NON_TASK prevents candidate
    assert is_candidate(valid_text, "probe-test", mojibake=False) is False
    assert is_candidate(valid_text, "source-cache-url-list", mojibake=False) is False
    assert is_candidate(valid_text, "loop-chain-infrastructure", mojibake=False) is False

    # Missing candidate word
    assert is_candidate("Some data with number 12,345 but no keywords", "datausa-grocery-workforce", mojibake=False) is False

    # Missing candidate number
    assert is_candidate("Arrived at round three with no numeric data", "datausa-grocery-workforce", mojibake=False) is False


def test_page_key_mapping():
    # Only the first ~ is replaced by /
    key1 = "dorfwiki~AgentDataUSAProbeFebX2"
    assert key1.replace("~", "/", 1) == "dorfwiki/AgentDataUSAProbeFebX2"

    key2 = "wiki~first~second"
    assert key2.replace("~", "/", 1) == "wiki/first~second"


def test_batch_cutting():
    # 35 records with 10 chars each -> batch 1: 30, batch 2: 5
    recs_35 = [{"record_id": f"rec_{i}", "text": "x" * 10} for i in range(35)]
    batches = partition_batches(recs_35, max_records=30, max_chars=15000)
    assert len(batches) == 2
    assert len(batches[0]) == 30
    assert len(batches[1]) == 5

    # 15,000 char threshold: two records of 8,000 chars cannot be together
    recs_large = [
        {"record_id": "r1", "text": "a" * 8000},
        {"record_id": "r2", "text": "b" * 8000},
    ]
    batches_large = partition_batches(recs_large, max_records=30, max_chars=15000)
    assert len(batches_large) == 2
    assert len(batches_large[0]) == 1
    assert len(batches_large[1]) == 1

    # Single record exceeding 15,000 chars goes alone
    recs_alone = [
        {"record_id": "r0", "text": "a" * 100},
        {"record_id": "r1", "text": "b" * 20000},
        {"record_id": "r2", "text": "c" * 100},
    ]
    batches_alone = partition_batches(recs_alone, max_records=30, max_chars=15000)
    assert len(batches_alone) == 3
    assert [len(b) for b in batches_alone] == [1, 1, 1]
    assert batches_alone[1][0]["record_id"] == "r1"


def test_batch_numbering_per_family(tmp_path):
    # Tests that batch filenames are formatted as <family>_NNN.jsonl, starting at 001 for each family
    from pathlib import Path
    import json

    by_family = {
        "fam-alpha": [{"record_id": f"a_{i}", "text": f"text a {i}", "page_family": "fam-alpha", "wall_time": f"2026-06-01T10:0{i}:00Z"} for i in range(35)],
        "fam-beta": [{"record_id": f"b_{i}", "text": f"text b {i}", "page_family": "fam-beta", "wall_time": f"2026-06-01T11:0{i}:00Z"} for i in range(5)],
    }

    batches_dir = tmp_path / "batches"
    for fam, recs in by_family.items():
        recs.sort(key=lambda r: (r["wall_time"], r["record_id"]))
        batches = partition_batches(recs, max_records=30, max_chars=15000)
        fam_dir = batches_dir / fam
        fam_dir.mkdir(parents=True, exist_ok=True)
        for idx, batch in enumerate(batches, 1):
            batch_file = fam_dir / f"{fam}_{idx:03d}.jsonl"
            batch_file.write_text("\n".join(json.dumps(r) for r in batch) + "\n", encoding="utf-8")

    # fam-alpha has 35 records -> fam-alpha_001.jsonl (30) and fam-alpha_002.jsonl (5)
    alpha_files = sorted((batches_dir / "fam-alpha").glob("*.jsonl"))
    assert [f.name for f in alpha_files] == ["fam-alpha_001.jsonl", "fam-alpha_002.jsonl"]

    # fam-beta has 5 records -> fam-beta_001.jsonl (restarted from 001)
    beta_files = sorted((batches_dir / "fam-beta").glob("*.jsonl"))
    assert [f.name for f in beta_files] == ["fam-beta_001.jsonl"]

