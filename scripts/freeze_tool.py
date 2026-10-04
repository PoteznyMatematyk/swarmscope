"""Create data/work/tool: a frozen copy of the package plus run.py, for sub-agents ("workers").

Workers must not run the live src/ tree: during the 2026-09-29 pilots an edit left cli.py with a SyntaxError for a
few seconds and a worker's verify call failed. run.py always uses this frozen copy and, unless --db is given,
data/work/snapshot.duckdb (a read-only copy of data/swarm.duckdb, so workers never contend with a writer).

    python scripts/freeze_tool.py              # re-run after EVERY change to src/ and before launching workers
    python scripts/freeze_tool.py --snapshot   # also (re)copy data/swarm.duckdb -> data/work/snapshot.duckdb (~0.8 GB)

Workers call:  <venv python> data/work/tool/run.py <subcommand> ...   (verify-claims, context, digest, audit-sample, ...)
"""

import argparse
import shutil
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
TOOL = ROOT / "data" / "work" / "tool"

RUN_PY = '''"""Frozen SwarmScope entry point for workers: always uses this copy of the code and the snapshot DB."""
import os
import pathlib
import sys

here = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(here))
os.environ.setdefault("SWARMSCOPE_TURNS_DB", str(here.parents[1] / "turns.duckdb"))  # data/turns.duckdb (layer C)
from swarmscope.cli import main  # noqa: E402

if "--db" not in sys.argv:
    sys.argv[1:1] = ["--db", str(here.parent / "snapshot.duckdb")]
main()
'''

parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
parser.add_argument("--snapshot", action="store_true")
args = parser.parse_args()

TOOL.mkdir(parents=True, exist_ok=True)
shutil.rmtree(TOOL / "swarmscope", ignore_errors=True)
shutil.copytree(ROOT / "swarmscope" / "src" / "swarmscope", TOOL / "swarmscope", ignore=shutil.ignore_patterns("__pycache__"))
(TOOL / "run.py").write_text(RUN_PY, encoding="utf-8")
print(f"frozen copy -> {TOOL}")
if args.snapshot:
    shutil.copy(ROOT / "data" / "swarm.duckdb", ROOT / "data" / "work" / "snapshot.duckdb")
    print("snapshot refreshed")
