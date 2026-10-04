"""Save the return value of a finished Workflow run (from its journal.jsonl or task output file) as JSON.

    python scripts/save_workflow_result.py <journal.jsonl | task.output> <out.json>

journal.jsonl holds one {"type":"result", ...} line per agent; the task output file holds the workflow's final return value.
"""

import json
import sys
from pathlib import Path

src, out = Path(sys.argv[1]), Path(sys.argv[2])
text = src.read_text(encoding="utf-8", errors="replace")
if src.suffix == ".jsonl":
    results = []
    for line in text.splitlines():
        try:
            rec = json.loads(line)
        except json.JSONDecodeError:
            continue
        if rec.get("type") == "result":
            results.append(rec)
    data = results
else:
    start = text.find("{")
    data, _ = json.JSONDecoder().raw_decode(text[start:])
    if isinstance(data, dict) and "result" in data and "agentCount" in data:  # task output wrapper -> the workflow's return value
        data = data["result"]
        if isinstance(data, str):
            data = json.loads(data)
out.parent.mkdir(parents=True, exist_ok=True)
out.write_text(json.dumps(data, indent=1, ensure_ascii=False), encoding="utf-8")
print(f"saved {out} ({out.stat().st_size} bytes)")
