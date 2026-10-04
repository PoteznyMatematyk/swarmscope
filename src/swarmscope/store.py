"""DuckDB-backed store for the unified schema."""

from __future__ import annotations

import json
from collections.abc import Iterable
from pathlib import Path

import duckdb
import pyarrow as pa

from .schema import DDL, Actor, Channel, Event

BATCH = 20000

# Columns whose type Arrow cannot infer reliably from Python values (e.g. all-None batches).
_ARROW_TYPES = {
    "ts": pa.timestamp("us", tz="UTC"),
    "ts_uncertainty_s": pa.float64(),
    "refs": pa.list_(pa.string()),
    "text": pa.string(),
    "parent_id": pa.string(),
    "subtype": pa.string(),
    "actor_id": pa.string(),
    "channel_id": pa.string(),
    "display_name": pa.string(),
    "model": pa.string(),
    "name": pa.string(),
    "extra": pa.string(),
}


class Store:
    def __init__(self, path: str | Path, read_only: bool = False):
        self.path = Path(path)
        if not read_only:
            self.path.parent.mkdir(parents=True, exist_ok=True)
        self.con = duckdb.connect(str(self.path), read_only=read_only)
        self.con.execute("SET TimeZone = 'UTC'")
        self.ref_index: dict[str, list[str]] | None = None  # filled lazily by evidence.resolve
        if not read_only:  # several read-only processes may share one file; only a writer migrates it
            self.con.execute(DDL)
            # databases created before ``subtype`` existed
            self.con.execute("ALTER TABLE events ADD COLUMN IF NOT EXISTS subtype VARCHAR")

    def clear_source(self, source: str) -> None:
        self.ref_index = None
        for table in ("events", "actors", "channels"):
            self.con.execute(f"DELETE FROM {table} WHERE source = ?", [source])

    def _insert(self, table: str, columns: list[str], rows: list[tuple]) -> None:
        """Bulk insert via an Arrow table (row-wise executemany is ~100x slower)."""
        if not rows:
            return
        batch = pa.Table.from_arrays(
            [pa.array(col, type=_ARROW_TYPES.get(name)) for name, col in zip(columns, zip(*rows))],
            names=columns,
        )
        self.con.register("_batch", batch)
        self.con.execute(
            f"INSERT OR REPLACE INTO {table} ({', '.join(columns)}) SELECT * FROM _batch"
        )
        self.con.unregister("_batch")

    def add_events(self, events: Iterable[Event]) -> int:
        self.ref_index = None
        cols = ["event_id", "source", "ts", "ts_uncertainty_s", "actor_id", "channel_id",
                "event_type", "subtype", "text", "parent_id", "refs", "raw_ref", "extra"]
        n, buf = 0, []
        for e in events:
            buf.append((e.event_id, e.source, e.ts, e.ts_uncertainty_s, e.actor_id, e.channel_id,
                        e.event_type, e.subtype, e.text, e.parent_id, e.refs, e.raw_ref,
                        json.dumps(e.extra)))
            if len(buf) >= BATCH:
                self._insert("events", cols, buf)
                n += len(buf)
                buf = []
        self._insert("events", cols, buf)
        return n + len(buf)

    def add_actors(self, actors: Iterable[Actor]) -> int:
        cols = ["actor_id", "source", "kind", "display_name", "model", "extra"]
        rows = [(a.actor_id, a.source, a.kind, a.display_name, a.model, json.dumps(a.extra))
                for a in actors]
        self._insert("actors", cols, rows)
        return len(rows)

    def add_channels(self, channels: Iterable[Channel]) -> int:
        cols = ["channel_id", "source", "kind", "name", "extra"]
        rows = [(c.channel_id, c.source, c.kind, c.name, json.dumps(c.extra)) for c in channels]
        self._insert("channels", cols, rows)
        return len(rows)

    def get_event(self, event_id: str) -> dict | None:
        cur = self.con.execute("SELECT * FROM events WHERE event_id = ?", [event_id])
        row = cur.fetchone()
        if row is None:
            return None
        return dict(zip([d[0] for d in cur.description], row))

    def stats(self) -> list[tuple]:
        return self.con.execute(
            """
            SELECT source, event_type, coalesce(subtype, '') AS subtype, count(*) AS n,
                   count(DISTINCT actor_id) AS actors, count(DISTINCT channel_id) AS channels,
                   min(ts) AS first_ts, max(ts) AS last_ts
            FROM events GROUP BY ALL ORDER BY source, n DESC
            """
        ).fetchall()
