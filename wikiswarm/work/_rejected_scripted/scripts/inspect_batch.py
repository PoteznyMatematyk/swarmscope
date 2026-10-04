import json
import sys
from pathlib import Path

batch_path = Path(sys.argv[1])
start = int(sys.argv[2]) if len(sys.argv) > 2 else 0
end = int(sys.argv[3]) if len(sys.argv) > 3 else 999999

records = [json.loads(line) for line in open(batch_path, encoding="utf-8") if line.strip()]
print(f"Viewing {batch_path.name} from index {start} to {min(end, len(records)) - 1} (total: {len(records)})")
for i in range(start, min(end, len(records))):
    r = records[i]
    print(f"=== Record {i} [{r['record_id']}] ===")
    print(r["text"])
    print()
