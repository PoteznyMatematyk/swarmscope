# /// script
# requires-python = ">=3.11"
# dependencies = ["huggingface_hub>=1.0"]
# ///
"""Fetch AI Village tables from Hugging Face (gated dataset: needs a token of an approved account).

    uv run scripts/fetch_ai_village.py docs       # docs + small tables                              (~0.1 MB)
    uv run scripts/fetch_ai_village.py analytic   # + events, chat, sessions, claude_code, transcript (~0.9 GB)
    uv run scripts/fetch_ai_village.py heavy      # + agent_memories, computer_use_turns              (~4.6 GB)

Screenshots (images/computer-use-turns/*.tar, ~159 GB) are never fetched here; pull single days on demand.
The token comes from HF_TOKEN or a previous `login()`; this script never stores it.
Raw data stays out of git (dataset terms: research only, no training, no re-identification).
"""

from __future__ import annotations

import argparse
import os
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

os.environ.setdefault("HF_HUB_DISABLE_PROGRESS_BARS", "1")  # per-file lines below are easier to tail

from huggingface_hub import HfApi, hf_hub_download  # noqa: E402

REPO = "aidigestorg/ai-village"
DEFAULT_DEST = Path(__file__).resolve().parents[2] / "data" / "raw" / "ai_village"

DOCS = ["README.md", "SCHEMA.md", "CHANGELOG.md", "example.py", "manifest.json",
        "images/computer-use-turns/index.json"]
SMALL = ["agents", "villages", "chat_rooms", "village_goals", "agent_goals", "claude_code_sessions"]
ANALYTIC = ["events", "chat_messages", "computer_use_sessions", "claude_code_messages", "summaries"]
HEAVY = ["agent_memories", "computer_use_turns"]


def _gz(stems: list[str]) -> list[str]:
    return [f"{s}.jsonl.gz" for s in stems]


TIERS = {
    "docs": DOCS + _gz(SMALL),
    "analytic": DOCS + _gz(SMALL + ANALYTIC) + ["village-transcript.json"],
    "heavy": DOCS + _gz(SMALL + ANALYTIC + HEAVY) + ["village-transcript.json"],
}


def fetch(filename: str, dest: Path) -> tuple[str, int, float]:
    t0 = time.perf_counter()
    path = hf_hub_download(REPO, filename, repo_type="dataset", local_dir=dest)
    return filename, Path(path).stat().st_size, time.perf_counter() - t0


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("tier", choices=sorted(TIERS))
    p.add_argument("--dest", type=Path, default=DEFAULT_DEST)
    p.add_argument("--workers", type=int, default=3)
    args = p.parse_args()

    print(f"hf user: {HfApi().whoami()['name']}  ->  {args.dest}", flush=True)
    args.dest.mkdir(parents=True, exist_ok=True)

    failed = 0
    with ThreadPoolExecutor(args.workers) as pool:
        jobs = {pool.submit(fetch, f, args.dest): f for f in TIERS[args.tier]}
        for job in as_completed(jobs):
            try:
                name, size, secs = job.result()
                print(f"  ok    {name:<44}{size / 1e6:>9.1f} MB {secs:>7.1f}s", flush=True)
            except Exception as exc:  # keep going: every failure is reported at the end
                failed += 1
                print(f"  FAIL  {jobs[job]:<44}{type(exc).__name__}: {str(exc)[:200]}", flush=True)
    print(f"done, {failed} failed", flush=True)
    sys.exit(1 if failed else 0)


if __name__ == "__main__":
    main()
