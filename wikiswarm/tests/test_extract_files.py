"""Tests for extraction files consistency."""
import json
from pathlib import Path
import pytest

ROOT = Path(__file__).resolve().parent.parent
WORK = ROOT / "work"


def test_extract_files_structure():
    extract_dir = WORK / "extract"
    if not extract_dir.exists():
        pytest.skip("No work/extract directory yet")

    extract_files = sorted(extract_dir.rglob("*.json"))
    if not extract_files:
        pytest.skip("No extract files yet")

    batches_dir = WORK / "batches"
    for ef in extract_files:
        rel = ef.relative_to(extract_dir).with_suffix(".jsonl")
        batch_file = batches_dir / rel
        assert batch_file.exists(), f"Batch file {batch_file} does not exist for extract {ef}"

        with open(ef, encoding="utf-8") as f:
            data = json.loads(f.read())

        assert data.get("batch") == rel.as_posix(), f"Mismatch in batch path for {ef}"

        batch_records = []
        with open(batch_file, encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line:
                    batch_records.append(json.loads(line))

        expected_ids = [r["record_id"] for r in batch_records]
        actual_ids = [r["record_id"] for r in data.get("records", [])]
        assert actual_ids == expected_ids, f"Records in {ef} do not match batch {batch_file}"
