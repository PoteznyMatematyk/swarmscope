"""Deep links into the live AI Village viewer: ``https://theaidigest.org/village?day={day}&time={unix_ms}``.

The village day number is not stored on events. ``village-transcript.json`` lists ``{"day": n, "date": "YYYY-MM-DD"}``
for every day; a day runs from about 17:00 UTC of its date until the next day starts, weekends are mostly skipped.
So an event belongs to the latest listed day whose date is not after ``(ts - 17 h).date()``.
"""

from __future__ import annotations

import bisect
import mmap
import re
from datetime import date, datetime, timedelta
from pathlib import Path

_DAY = re.compile(rb'"day":\s*(\d+),\s*"date":\s*"(\d{4}-\d{2}-\d{2})"')
BASE = "https://theaidigest.org/village"
SHIFT = timedelta(hours=17)


def build_day_map(transcript: Path) -> dict[str, int]:
    """``{"2025-04-02": 1, ...}`` from ``village-transcript.json`` (memory-mapped scan, no JSON parse)."""
    with open(transcript, "rb") as fh, mmap.mmap(fh.fileno(), 0, access=mmap.ACCESS_READ) as mm:
        return {m.group(2).decode(): int(m.group(1)) for m in _DAY.finditer(mm)}


def village_day(ts: datetime, day_map: dict[str, int]) -> int | None:
    dates = sorted(day_map)
    key = (ts - SHIFT).date().isoformat()
    i = bisect.bisect_right(dates, key) - 1
    return day_map[dates[i]] if i >= 0 else None


def deeplink(ts: datetime, day_map: dict[str, int]) -> str | None:
    day = village_day(ts, day_map)
    return None if day is None else f"{BASE}?day={day}&time={int(ts.timestamp() * 1000)}"


def load_day_map(path: Path) -> dict[str, int]:
    import json
    return json.loads(path.read_text(encoding="utf-8"))
