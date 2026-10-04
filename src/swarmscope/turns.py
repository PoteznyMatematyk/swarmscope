"""Layer C: computer-use turns and agent memories ("what agents DID" and "what they remembered").

The event timeline (``events``) holds what agents *said*. The 2.5M computer-use turns hold the executed actions and tool
output. They live in a separate slim DuckDB (``turns.duckdb``) so the citation store stays small and the raw reasoning
(``agent_messages``, ~80% of the bytes) is never copied.

    swarmscope ingest-turns --raw ../data/raw/ai_village --out ../data/turns.duckdb
    swarmscope actions --agent "Claude Opus 4.7" --start 2026-06-01T10:00 --end 2026-06-01T12:00 [--types bash,type] [--grep v8]
    swarmscope memories --agent "GPT-5.5" --start 2026-06-01 --end 2026-06-02 [--grep checkpoint]
    swarmscope cite-turn <turn_ref> "<verbatim quote from the action or its output>"

A turn is cited by its 10-hex handle (first hex characters of the turn uuid), like events. ``cite-turn`` applies the same
deterministic rule as ``evidence.py``: the quote must occur verbatim (whitespace/quote-normalised, whole words) in the
turn's action text, output or error.
"""

from __future__ import annotations

import time
from pathlib import Path

import duckdb

from .evidence import MIN_QUOTE_CHARS, MAX_QUOTE_WORDS, find_quote, normalize

MAX_OBJECT = 268_435_456  # single JSONL rows carry raw model messages
ACTION_CHARS, OUT_CHARS, ERR_CHARS, MEMORY_CHARS = 800, 600, 300, 8000
TAIL_CHARS = 600  # summaries (pytest "N passed", build results) sit at the END of long outputs


def _q(path: Path) -> str:
    return str(path).replace("\\", "/").replace("'", "''")


def ingest_turns(raw: Path, out: Path) -> dict:
    """Build the slim turns database from the raw jsonl.gz tables (needs agents, computer_use_sessions, computer_use_turns, agent_memories)."""
    raw, out = Path(raw), Path(out)
    out.parent.mkdir(parents=True, exist_ok=True)
    if out.exists():
        out.unlink()
    con = duckdb.connect(str(out))
    con.execute("SET TimeZone = 'UTC'")
    stats: dict = {}
    t0 = time.perf_counter()
    ts = lambda col: f"(({col})::TIMESTAMP AT TIME ZONE 'UTC')"

    con.execute(f"""CREATE TABLE agents AS SELECT id AS agent_id, name, model_string
        FROM read_ndjson('{_q(raw / 'agents.jsonl.gz')}', columns={{'id':'VARCHAR','name':'VARCHAR','model_string':'VARCHAR'}})""")
    con.execute(f"""CREATE TABLE sessions AS SELECT id AS session_id, agent_id, session_goal, {ts('created_at')} AS ts
        FROM read_ndjson('{_q(raw / 'computer_use_sessions.jsonl.gz')}',
        columns={{'id':'VARCHAR','agent_id':'VARCHAR','session_goal':'VARCHAR','created_at':'VARCHAR'}})""")
    stats["agents"] = con.execute("SELECT count(*) FROM agents").fetchone()[0]
    stats["sessions"] = con.execute("SELECT count(*) FROM sessions").fetchone()[0]

    act = "t.agent_action"
    con.execute(f"""CREATE TABLE turns AS
        SELECT t.id AS turn_id, substr(replace(t.id, '-', ''), 1, 10) AS ref, t.session_id, s.agent_id, a.name AS agent,
               {ts('t.created_at')} AS ts,
               coalesce(json_extract_string({act}, '$.action'),
                        CASE WHEN json_extract_string({act}, '$.command') IS NOT NULL THEN 'bash' END) AS action_type,
               substr(coalesce(json_extract_string({act}, '$.text'), json_extract_string({act}, '$.command'),
                               json_extract_string({act}, '$.keys'), json_extract_string({act}, '$.url'), ''), 1, {ACTION_CHARS}) AS action_text,
               substr(t.output, 1, {OUT_CHARS}) AS out_text,
               CASE WHEN length(t.output) > {OUT_CHARS} THEN right(t.output, {TAIL_CHARS}) END AS out_tail,
               substr(t.error, 1, {ERR_CHARS}) AS err_text
        FROM read_ndjson('{_q(raw / 'computer_use_turns.jsonl.gz')}',
             columns={{'id':'VARCHAR','session_id':'VARCHAR','agent_action':'JSON','output':'VARCHAR','error':'VARCHAR','created_at':'VARCHAR'}},
             maximum_object_size={MAX_OBJECT}) t
        LEFT JOIN sessions s ON s.session_id = t.session_id LEFT JOIN agents a ON a.agent_id = s.agent_id""")
    stats["turns"] = con.execute("SELECT count(*) FROM turns").fetchone()[0]
    stats["turns_with_action"] = con.execute("SELECT count(*) FROM turns WHERE action_type IS NOT NULL").fetchone()[0]

    con.execute(f"""CREATE TABLE memories AS
        SELECT m.id AS memory_id, substr(replace(m.id, '-', ''), 1, 10) AS ref, m.agent_id, a.name AS agent, {ts('m.created_at')} AS ts,
               substr(m.content, 1, {MEMORY_CHARS}) AS text, length(m.content) AS full_chars
        FROM read_ndjson('{_q(raw / 'agent_memories.jsonl.gz')}',
             columns={{'id':'VARCHAR','content':'VARCHAR','agent_id':'VARCHAR','created_at':'VARCHAR'}}, maximum_object_size={MAX_OBJECT}) m
        LEFT JOIN agents a ON a.agent_id = m.agent_id""")
    stats["memories"] = con.execute("SELECT count(*) FROM memories").fetchone()[0]
    con.execute("CREATE INDEX turns_ref ON turns(ref)")
    con.execute("CREATE INDEX turns_agent_ts ON turns(agent, ts)")
    con.execute("CREATE INDEX memories_agent_ts ON memories(agent, ts)")
    stats["seconds"] = round(time.perf_counter() - t0, 1)
    con.close()
    return stats


def open_turns(path: str | Path) -> duckdb.DuckDBPyConnection:
    con = duckdb.connect(str(path), read_only=True)
    con.execute("SET TimeZone = 'UTC'")
    return con


def _clip(text: str | None, n: int) -> str:
    text = " ".join((text or "").split())
    return text if len(text) <= n else text[:n] + f"...[+{len(text) - n} chars]"


def _clip_end(text: str | None, n: int) -> str:
    text = " ".join((text or "").split())
    return text if len(text) <= n else f"[{len(text) - n} chars]..." + text[-n:]


def actions(con, agent: str, start: str, end: str, types: list[str] | None = None, grep: str | None = None,
            limit: int = 200, max_chars: int = 300) -> list[str]:
    """One line per executed turn of an agent in [start, end) UTC: ``[ts] {ref} type: action | out: ...``."""
    where, params = ["lower(agent) LIKE ?", "ts >= ?::TIMESTAMPTZ", "ts < ?::TIMESTAMPTZ", "action_type IS NOT NULL"], [f"%{agent.lower()}%", start, end]
    if types:
        where.append(f"action_type IN ({', '.join('?' * len(types))})")
        params += types
    if grep:
        where.append("(lower(action_text) LIKE ? OR lower(coalesce(out_text,'')) LIKE ? OR lower(coalesce(out_tail,'')) LIKE ?)")
        params += [f"%{grep.lower()}%"] * 3
    rows = con.execute(f"SELECT ts, ref, agent, action_type, action_text, out_text, out_tail, err_text FROM turns WHERE {' AND '.join(where)} ORDER BY ts LIMIT {int(limit)}", params).fetchall()
    out = []
    for ts, ref, ag, typ, text, o, otail, err in rows:
        tail = (f" | out: {_clip(o, max_chars)}" if o else "") + (f" | out-end: {_clip_end(otail, max_chars // 2)}" if otail else "") \
            + (f" | err: {_clip(err, 120)}" if err else "")
        out.append(f"[{ts:%m-%d %H:%M:%S}] {{{ref}}} {ag} {typ}: {_clip(text, max_chars)}{tail}")
    return out


def memories(con, agent: str, start: str, end: str, grep: str | None = None, limit: int = 50, max_chars: int = 1200) -> list[str]:
    where, params = ["lower(agent) LIKE ?", "ts >= ?::TIMESTAMPTZ", "ts < ?::TIMESTAMPTZ"], [f"%{agent.lower()}%", start, end]
    if grep:
        where.append("lower(text) LIKE ?")
        params.append(f"%{grep.lower()}%")
    rows = con.execute(f"SELECT ts, ref, agent, text, full_chars FROM memories WHERE {' AND '.join(where)} ORDER BY ts LIMIT {int(limit)}", params).fetchall()
    return [f"[{ts:%m-%d %H:%M:%S}] {{{ref}}} {ag} memory ({n} chars): {_clip(text, max_chars)}" for ts, ref, ag, text, n in rows]


def get_turn(con, ref: str) -> dict | None:
    """The single turn behind a 10-hex handle, or None (missing or ambiguous)."""
    ref = ref.strip().lower().replace("-", "")[:10]
    cur = con.execute("SELECT turn_id, ts, agent, action_type, action_text, out_text, out_tail, err_text FROM turns WHERE ref = ?", [ref])
    rows = cur.fetchall()
    return dict(zip([d[0] for d in cur.description], rows[0])) if len(rows) == 1 else None


def verify_turn_quote(con, ref: str, quote: str) -> str:
    """Status of a (turn ref, quote) pair: verified | event_missing | ambiguous_ref | empty_quote | quote_too_short | quote_too_long | quote_not_found."""
    ref = ref.strip().lower().replace("-", "")
    rows = con.execute("SELECT action_text, out_text, out_tail, err_text FROM turns WHERE ref = ?", [ref[:10]]).fetchall() if len(ref) >= 10 else []
    if not rows:
        return "event_missing"
    if len(rows) > 1:
        return "ambiguous_ref"
    needle = normalize(quote)
    if not needle:
        return "empty_quote"
    if len(needle) < MIN_QUOTE_CHARS:
        return "quote_too_short"
    if len(needle.split()) > MAX_QUOTE_WORDS:
        return "quote_too_long"
    hay = [normalize(t) for t in rows[0] if t]
    return "verified" if any(find_quote(h, needle) >= 0 for h in hay) else "quote_not_found"
