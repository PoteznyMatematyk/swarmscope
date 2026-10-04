"""Episode context files: village goals, private goals, roster, rooms, dated scaffolding changes."""
import gzip
import json
import re
from datetime import date, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2] / "data"
RAW = ROOT / "raw/ai_village"
manifest = json.loads((ROOT / "work/windows/manifest.json").read_text(encoding="utf-8"))


def rows(name):
    return [json.loads(l) for l in gzip.open(RAW / name, "rt", encoding="utf-8")]


agents = {a["id"]: a for a in rows("agents.jsonl.gz")}
goals = sorted(rows("village_goals.jsonl.gz"), key=lambda g: g["start_time"])
private = sorted(rows("agent_goals.jsonl.gz"), key=lambda g: str(g["start_time"] or g["created_at"]))
rooms = rows("chat_rooms.jsonl.gz")

# CHANGELOG: split into dated sections
text = (RAW / "CHANGELOG.md").read_text(encoding="utf-8")
sections = []
for m in re.finditer(r"^## (\d{4}-\d{2}-\d{2})[^\n]*\n(.*?)(?=^## |\Z)", text, re.S | re.M):
    sections.append((date.fromisoformat(m.group(1)), m.group(0).strip()))


def d(s):
    return date.fromisoformat(s)


for name, ep in manifest.items():
    start, end = d(ep["start"]), d(ep["end"])
    out = [f"# Context for {name}  (window {ep['start']} .. {ep['end']} UTC)", "",
           "Setting: AI Village - frontier-model agents share a group chat, each has its own computer, memory that is",
           "consolidated periodically, and a village-wide goal. Timestamps in the log are UTC.", ""]
    out.append("## Village goals overlapping the window")
    for g in goals:
        gs = d(g["start_time"][:10])
        ge = d(g["end_time"][:10]) if g["end_time"] else date(2100, 1, 1)
        if gs < end and ge > start:
            out.append(f"- {g['start_time'][:10]} -> {(g['end_time'] or 'ongoing')[:10]}: {g['goal']}")
    active_private = [p for p in private if d(str(p['start_time'] or p['created_at'])[:10]) < end]
    if active_private:
        out += ["", "## Private per-agent goals (each agent sees only its own; assigned by the organisers)"]
        for p in active_private:
            who = agents.get(p["agent_id"], {}).get("name", "?")
            extra = f" -- {p['description']}" if p.get("description") else ""
            out.append(f"- {who} (from {str(p['start_time'] or p['created_at'])[:10]}): {p['name']} [{p['short_name']}]{extra}")
    out += ["", "## Agents that joined on or before the window end (name; model; joined)"]
    for a in sorted(agents.values(), key=lambda a: a["created_at"]):
        if d(a["created_at"][:10]) < end:
            out.append(f"- {a['name']}; {a['model_string']}; joined {a['created_at'][:10]}")
    out += ["", "## Chat rooms (name; created; deleted; whitelist / blacklist)"]
    for r in sorted(rooms, key=lambda r: r["created_at"]):
        if d(r["created_at"][:10]) < end and (not r["deleted_at"] or d(r["deleted_at"][:10]) > start):
            out.append(f"- #{r['name']}; {r['created_at'][:10]}; {str(r['deleted_at'])[:10]}; "
                       f"wl={r['whitelisted_agent_names']} bl={r['blacklisted_agent_names']}")
    out += ["", "## Scaffolding changes near the window (from the dataset CHANGELOG; 4 days before start .. end)"]
    near = [s for dt, s in sections if start - timedelta(days=4) <= dt <= end]
    out += near if near else ["(none listed)"]
    out += ["", "## Reading notes",
            "- Times in the log are UTC; agents talk in Pacific time (UTC-7 in summer, UTC-8 in winter).",
            "- Handles such as 'admin' belong to organiser staff; 'automated' is the auto-nudge bot. Do not guess who anyone is.",
            "- A chat room can carry its own goal/kickoff override (see scaffolding changes); the first messages of a room often show it.",
            "- Structured events (<OUTREACH_APPROVAL_REQUEST>, <OUTREACH_APPROVAL_RESPONSE req=...>, etc.) are labelled by subtype;",
            "  a decision's `req=` id equals its request's id, and the decision line is labelled ADMIN-DECISION->agent.",
            "", "## Standing caveats from the dataset authors",
            "- Agents sometimes mis-see, misunderstand or misreport what happened; narration is a claim, not ground truth.",
            "- From 2026-02-10 an auto-nudger bot may post corrective 'nudge' messages (scaffolding, not human).",
            "- From 2026-02-25 agents only see the room they are in (rooms v1).",
            "- Secrets are redacted as [REDACTED]; long messages are truncated in this log ('...[+N chars]')."]
    path = ROOT / "work/windows" / name / "context.md"
    body = re.sub(r"http://10\.\d+\.\d+\.\d+:\d+/\S*", "[internal-url]", "\n".join(out))  # private infra addresses
    path.write_text(body + "\n", encoding="utf-8")
    ep["context"] = str(path).replace("\\", "/")
    print(f"{name}: context {path.stat().st_size} bytes")

(ROOT / "work/windows/manifest.json").write_text(json.dumps(manifest, indent=1), encoding="utf-8")
