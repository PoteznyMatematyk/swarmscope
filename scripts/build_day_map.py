"""Build data/day_map.json (date -> AI Village day number) from village-transcript.json.

    python scripts/build_day_map.py            # run from the swarmscope directory with the project venv

The map is what turns an event timestamp into a deep link (https://theaidigest.org/village?day=..&time=..).
"""

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "swarmscope" / "src"))
from swarmscope.links import build_day_map  # noqa: E402

day_map = build_day_map(ROOT / "data" / "raw" / "ai_village" / "village-transcript.json")
(ROOT / "data" / "day_map.json").write_text(json.dumps(day_map), encoding="utf-8")
print(f"{len(day_map)} days, {min(day_map)} -> {max(day_map)}")
