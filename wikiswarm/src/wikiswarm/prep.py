"""Data preparation for wikiswarm: builds posts table and extraction batches."""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

# Paths relative to the wikiswarm root; the data folder is resolved once, in gate/common.py
ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT))
from gate.common import DATA  # noqa: E402

WORK = ROOT / "work"

SIG_RE = re.compile(r"--\s*([A-Za-z][A-Za-z0-9_\-]{2,60})")
MOJIBAKE_CHARS = ("Ã", "â€", "Â")
CAND_WORDS = re.compile(
    r"(\bR\d{1,2}\b|\bG\d{1,2}\b|#\d{1,2}\b|\bround|\bsequence|->|\bSTATE\d|\bconfirmed|\banswered|\barrived|\bprompt)",
    re.IGNORECASE,
)
CAND_NUMBER = re.compile(r"\d[\d,\.]*\d")
NON_TASK = {
    "source-cache-url-list",
    "source-or-unclassified",
    "off_store_unclassified",
    "loop-chain-infrastructure",
    "probe-test",
    "unknown",
}


def load_page_map(pages_path: Path = DATA / "pages.jsonl") -> dict[str, str]:
    page_map = {}
    with open(pages_path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            p = json.loads(line)
            key = p["page_key"].replace("~", "/", 1)
            page_map[key] = p.get("page_family", "unmapped")
    return page_map


def extract_signature(text: str) -> str | None:
    matches = list(SIG_RE.finditer(text))
    return matches[-1].group(1) if matches else None


def is_mojibake(text: str) -> bool:
    return any(m in text for m in MOJIBAKE_CHARS)


def is_candidate(text: str, page_family: str, mojibake: bool) -> bool:
    if mojibake:
        return False
    if page_family in NON_TASK:
        return False
    if not CAND_WORDS.search(text):
        return False
    if not CAND_NUMBER.search(text):
        return False
    return True


def build_posts(
    records_path: Path = DATA / "records.jsonl",
    pages_path: Path = DATA / "pages.jsonl",
) -> list[dict]:
    page_map = load_page_map(pages_path)
    posts = []
    with open(records_path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            rec = json.loads(line)
            rec_id = rec["id"]
            text = rec["text"]
            mojibake = is_mojibake(text)
            sig = extract_signature(text)

            for i, origin in enumerate(rec.get("origins", [])):
                src_id = origin.get("source_id")
                page_fam = page_map.get(src_id, "unmapped")
                wall_time = origin.get("source_date_literal")
                cand = is_candidate(text, page_fam, mojibake)
                posts.append({
                    "post_id": f"{rec_id}:{i}",
                    "record_id": rec_id,
                    "origin_index": i,
                    "text": text,
                    "source_id": src_id,
                    "page_family": page_fam,
                    "wall_time": wall_time,
                    "signature": sig,
                    "mojibake": mojibake,
                    "candidate": cand,
                })
    posts.sort(key=lambda p: (p["wall_time"], p["post_id"]))
    return posts


def partition_batches(recs: list[dict], max_records: int = 30, max_chars: int = 15000) -> list[list[dict]]:
    batches = []
    cur_batch = []
    cur_chars = 0
    for r in recs:
        rlen = len(r["text"])
        if not cur_batch:
            cur_batch.append(r)
            cur_chars += rlen
            if rlen > max_chars:
                batches.append(cur_batch)
                cur_batch = []
                cur_chars = 0
        else:
            if len(cur_batch) >= max_records or (cur_chars + rlen > max_chars):
                batches.append(cur_batch)
                cur_batch = [r]
                cur_chars = rlen
                if rlen > max_chars:
                    batches.append(cur_batch)
                    cur_batch = []
                    cur_chars = 0
            else:
                cur_batch.append(r)
                cur_chars += rlen
    if cur_batch:
        batches.append(cur_batch)
    return batches


def main() -> None:
    WORK.mkdir(parents=True, exist_ok=True)
    posts = build_posts()
    posts_path = WORK / "posts.jsonl"
    with open(posts_path, "w", encoding="utf-8") as f:
        for p in posts:
            f.write(json.dumps(p, ensure_ascii=False) + "\n")
    print(f"Wrote {len(posts)} posts to {posts_path}")

    # Unit of extraction = a candidate record (a record with at least one candidate post),
    # taken once, with the data of its earliest candidate post (first in the sorted posts order)
    candidate_recs: dict[str, dict] = {}
    for p in posts:
        if p["candidate"] and p["record_id"] not in candidate_recs:
            candidate_recs[p["record_id"]] = {
                "record_id": p["record_id"],
                "text": p["text"],
                "page_family": p["page_family"],
                "wall_time": p["wall_time"],
            }
    print(f"Total candidate records: {len(candidate_recs)}")

    # Group by page_family, sort by (wall_time, record_id), cut into batches
    by_family: dict[str, list[dict]] = {}
    for r in candidate_recs.values():
        by_family.setdefault(r["page_family"], []).append(r)

    batches_dir = WORK / "batches"
    batches_dir.mkdir(parents=True, exist_ok=True)

    total_batch_files = 0
    for fam in sorted(by_family):
        recs = by_family[fam]
        recs.sort(key=lambda r: (r["wall_time"], r["record_id"]))
        batches = partition_batches(recs, max_records=30, max_chars=15000)
        fam_dir = batches_dir / fam
        fam_dir.mkdir(parents=True, exist_ok=True)
        for idx, batch in enumerate(batches, 1):
            batch_file = fam_dir / f"{fam}_{idx:03d}.jsonl"
            with open(batch_file, "w", encoding="utf-8") as f:
                for r in batch:
                    f.write(json.dumps(r, ensure_ascii=False) + "\n")
            total_batch_files += 1

    print(f"Wrote {total_batch_files} batch files across {len(by_family)} families.")


if __name__ == "__main__":
    main()
