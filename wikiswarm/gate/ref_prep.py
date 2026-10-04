"""Reference implementation of stage S1 (posts table). The gate compares the pipeline's
work/posts.jsonl with this, field by field. Spec: SPEC.md section S1."""
from __future__ import annotations

from common import CAND_NUMBER, CAND_WORDS, DATA, MOJIBAKE, SIG_RE, read_jsonl

NON_TASK = {"source-cache-url-list", "source-or-unclassified", "off_store_unclassified",
            "loop-chain-infrastructure", "probe-test", "unknown"}


def page_families() -> dict[str, str]:
    return {p["page_key"].replace("~", "/", 1): p["page_family"] for p in read_jsonl(DATA / "pages.jsonl")}


def build_posts() -> list[dict]:
    fam = page_families()
    posts = []
    for r in read_jsonl(DATA / "records.jsonl"):
        text = r["text"]
        sigs = SIG_RE.findall(text)
        moj = any(m in text for m in MOJIBAKE)
        for i, o in enumerate(r["origins"]):
            pf = fam.get(o["source_id"], "unmapped")
            cand = (not moj and pf not in NON_TASK and CAND_WORDS.search(text) is not None
                    and CAND_NUMBER.search(text) is not None)
            posts.append({
                "post_id": f"{r['id']}:{i}", "record_id": r["id"], "origin_index": i, "text": text,
                "source_id": o["source_id"], "page_family": pf, "wall_time": o["source_date_literal"],
                "signature": sigs[-1] if sigs else None, "mojibake": moj, "candidate": cand,
            })
    posts.sort(key=lambda p: (p["wall_time"], p["post_id"]))
    return posts


if __name__ == "__main__":
    import collections
    ps = build_posts()
    c = [p for p in ps if p["candidate"]]
    print("posts", len(ps), "candidates", len(c), "chars", sum(len(p["text"]) for p in c))
    print(collections.Counter(p["page_family"] for p in c).most_common(30))
