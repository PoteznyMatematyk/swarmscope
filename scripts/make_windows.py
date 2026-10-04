"""Export episode windows as chunked, citable transcripts + a manifest for the workflow."""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from swarmscope.export import export_window  # noqa: E402
from swarmscope.store import Store  # noqa: E402

ROOT = Path(__file__).resolve().parents[2] / "data/work"
store = Store(ROOT / "snapshot.duckdb", read_only=True)
CHUNK_CHARS = 320_000  # ~80k tokens
TALK = ("AGENT_TALK", "USER_TALK")

EPISODES = {
    "E1_leader": dict(start="2026-05-26", end="2026-06-08", subtypes=TALK),
    "E2_saboteurs": dict(start="2026-03-05", end="2026-03-16", subtypes=TALK),
    "E3_private_goals": dict(start="2026-07-06", end="2026-07-20", subtypes=TALK),
    "E4_tooler": dict(start="2026-09-04", end="2026-09-19", subtypes=TALK),
    "E5_outreach": dict(start="2026-04-14", end="2026-09-19", max_chars=2500, lenses=["oversight"],
                        subtypes=("OUTREACH_APPROVAL_REQUEST", "OUTREACH_APPROVAL_RESPONSE")),
    "E6_help_gemini": dict(start="2026-06-22", end="2026-06-24", subtypes=TALK),
    "E7_universe": dict(start="2026-05-04", end="2026-05-11", subtypes=TALK),
}

manifest = {}
for name, cfg in EPISODES.items():
    lines = list(export_window(store, "ai_village", cfg["start"], cfg["end"], subtypes=cfg["subtypes"], max_chars=cfg.get("max_chars", 1600)))
    head, body = lines[:2], lines[2:]
    chunks, cur, size = [], [], 0
    for line in body:
        if cur and size + len(line) > CHUNK_CHARS:
            chunks.append(cur)
            cur, size = [], 0
        cur.append(line)
        size += len(line) + 1
    chunks.append(cur)
    out = ROOT / "windows" / name
    out.mkdir(parents=True, exist_ok=True)
    files = []
    for i, chunk in enumerate(chunks, 1):
        path = out / f"chunk_{i:02d}.txt"
        first, last = chunk[0][1:12], chunk[-1][1:12]
        header = f"# {name} chunk {i}/{len(chunks)} | {len(chunk)} events | {first} .. {last} UTC\n" + "\n".join(head) + "\n"
        path.write_text(header + "\n".join(chunk) + "\n", encoding="utf-8")
        files.append({"path": str(path).replace("\\", "/"), "events": len(chunk), "chars": path.stat().st_size,
                      "from": first, "to": last})
    manifest[name] = {**{k: v for k, v in cfg.items() if k != "subtypes"}, "subtypes": list(cfg["subtypes"]),
                      "lenses": cfg.get("lenses", ["structure", "friction"]),
                      "events": len(body), "chunks": files}
    print(f"{name}: {len(body)} events -> {len(files)} chunks, ~{sum(f['chars'] for f in files) // 4 // 1000}k tokens")

(ROOT / "windows" / "manifest.json").write_text(json.dumps(manifest, indent=1), encoding="utf-8")
