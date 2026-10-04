"""Shared helpers for reading raw files."""

from __future__ import annotations

import gzip
import json
from collections.abc import Iterator
from datetime import datetime, timezone
from pathlib import Path


def read_jsonl(path: Path, contains: str | None = None) -> Iterator[tuple[int, dict]]:
    """Yield ``(line_number, record)`` from ``.jsonl`` or ``.jsonl.gz``.

    ``contains`` skips lines without that substring before parsing (cheap pre-filter for huge files;
    the caller still has to confirm the match on the parsed record).
    """
    opener = gzip.open if path.suffix == ".gz" else open
    with opener(path, "rt", encoding="utf-8") as fh:
        for lineno, line in enumerate(fh, 1):
            if line.strip() and (contains is None or contains in line):
                yield lineno, json.loads(line)


def find(raw_dir: Path, stem: str) -> Path | None:
    """Locate ``stem`` as plain or gzipped file."""
    for candidate in (raw_dir / stem, raw_dir / f"{stem}.gz"):
        if candidate.exists():
            return candidate
    return None


def parse_ts(value) -> datetime | None:
    if value in (None, ""):
        return None
    if isinstance(value, (int, float)):
        # epoch seconds or milliseconds
        return datetime.fromtimestamp(value / 1000 if value > 1e11 else value, tz=timezone.utc)
    parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    # AI Village exports UTC without a zone suffix ("2025-12-29 18:49:21.291984")
    return parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)
