"""Deterministic citation checking.

LLM answers must cite ``(event_id, quote)`` pairs. Before any claim is shown,
``verify_citation`` checks that the event exists and that the quote literally
appears in its text (after whitespace/quote normalisation). No model is involved,
so a hallucinated citation can never pass.

``event_id`` may be the full id or the short ref printed by ``export`` (the first
hex characters of the uuid embedded in the id, hyphens ignored); a ref matching
several events is rejected.
"""

from __future__ import annotations

import collections
import re
import unicodedata
from dataclasses import dataclass

from .store import Store

_QUOTES = str.maketrans({"‘": "'", "’": "'", "“": '"', "”": '"', " ": " ", "⏎": " "})
_REF = re.compile(r"[0-9a-f-]{8,40}")
_KEY = 8  # characters of the hyphen-less uuid used as the index key
MIN_QUOTE_CHARS = 8  # normalised; shorter "quotes" ("yes", "ok") match almost anything and prove nothing
MAX_QUOTE_WORDS = 60  # a "quote" that is a whole message proves nothing about a specific claim


def _tail(event_id: str) -> str:
    return event_id.rsplit(":", 1)[-1].replace("-", "")


def ref_of(event_id: str) -> str:
    """Short citation handle: the first 10 hex characters of the uuid embedded in ``event_id``."""
    return _tail(event_id)[:10]


def normalize(text: str) -> str:
    text = unicodedata.normalize("NFKC", text).translate(_QUOTES)
    return re.sub(r"\s+", " ", text).strip().lower()


@dataclass
class CitationCheck:
    event_id: str
    quote: str
    status: str  # "verified" | "event_missing" | "ambiguous_ref" | "no_text" | "quote_not_found" | "empty_quote" | "quote_too_short" | "quote_too_long"
    offset: int | None = None


def _index(store: Store) -> dict[str, list[str]]:
    """Prefix index over all event ids (built once per store state, dropped by ``Store.add_events``)."""
    if store.ref_index is None:
        store.ref_index = collections.defaultdict(list)
        for (event_id,) in store.con.execute("SELECT event_id FROM events").fetchall():
            store.ref_index[_tail(event_id)[:_KEY]].append(event_id)
    return store.ref_index


def find_quote(text: str, quote: str) -> int:
    """Offset of ``quote`` in ``text`` (both normalised) or -1. The match must start and end on a word boundary,
    so "not" is not found inside "another"."""
    edge = lambda ch: ch.isalnum() or ch == "_"
    pattern = (r"(?<![\w])" if edge(quote[0]) else "") + re.escape(quote) + (r"(?![\w])" if edge(quote[-1]) else "")
    m = re.search(pattern, text)
    return m.start() if m else -1


def resolve(store: Store, ref: str) -> list[str]:
    """Full ids matching ``ref`` (an exact id, or a hex prefix of the uuid embedded in it)."""
    if store.get_event(ref) is not None:
        return [ref]
    ref = ref.strip().lower()
    if not _REF.fullmatch(ref) or len(ref.replace("-", "")) < _KEY:
        return []
    ref = ref.replace("-", "")
    return [e for e in _index(store).get(ref[:_KEY], []) if _tail(e).startswith(ref)]


def verify_citation(store: Store, event_id: str, quote: str) -> CitationCheck:
    matches = resolve(store, event_id)
    if not matches:
        return CitationCheck(event_id, quote, "event_missing")
    if len(matches) > 1:
        return CitationCheck(event_id, quote, "ambiguous_ref")
    event = store.get_event(matches[0])
    needle = normalize(quote)
    if not needle:
        return CitationCheck(matches[0], quote, "empty_quote")
    if not event.get("text"):
        return CitationCheck(matches[0], quote, "no_text")
    if len(needle) < MIN_QUOTE_CHARS:
        return CitationCheck(matches[0], quote, "quote_too_short")
    if len(needle.split()) > MAX_QUOTE_WORDS:
        return CitationCheck(matches[0], quote, "quote_too_long")
    offset = find_quote(normalize(event["text"]), needle)
    if offset < 0:
        return CitationCheck(matches[0], quote, "quote_not_found", None)
    return CitationCheck(matches[0], quote, "verified", offset)
