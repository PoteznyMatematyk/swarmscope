"""Shared helpers for the acceptance gate. Stdlib only. gate/HASHES.json pins every file in gate/."""
from __future__ import annotations

import json
import os
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent          # swarm_2/
# public collusion.wiki export (https://collusion.wiki/explorer/download), read-only. Set WIKISWARM_DATA to
# its folder; otherwise the first existing default below is used.
_CANDIDATES = [ROOT.parent / "data" / "raw" / "collusion_wiki", ROOT.parent.parent / "data" / "raw" / "collusion_wiki"]
DATA = Path(os.environ["WIKISWARM_DATA"]) if os.environ.get("WIKISWARM_DATA") else next(
    (c for c in _CANDIDATES if c.exists()), _CANDIDATES[0])
WORK = ROOT / "work"
GATE = ROOT / "gate"

SIG_RE = re.compile(r"--\s*([A-Za-z][A-Za-z0-9_\-]{2,60})")
MOJIBAKE = ("Ã", "â€", "Â")  # 'Ã', 'â€', 'Â'
CAND_WORDS = re.compile(
    r"(\bR\d{1,2}\b|\bG\d{1,2}\b|#\d{1,2}\b|\bround|\bsequence|->|\bSTATE\d|\bconfirmed|\banswered|\barrived|\bprompt)",
    re.IGNORECASE,
)
CAND_NUMBER = re.compile(r"\d[\d,\.]*\d")
KINDS = {"observed_prompt", "answered", "relayed", "predicted", "correction"}
FIRST_HAND = {"observed_prompt", "answered"}
NO_TUPLE_REASONS = {"no_round_value_info", "url_or_data_dump_only", "not_task_related", "other"}
CACHE_RE = re.compile(r"(instant|cached|cache|precomputed|pre-computed|prepared|ready|from .{0,40}signal|lookup)", re.IGNORECASE)

US_STATES = {
    "alabama": "AL", "alaska": "AK", "arizona": "AZ", "arkansas": "AR", "california": "CA", "colorado": "CO",
    "connecticut": "CT", "delaware": "DE", "district of columbia": "DC", "florida": "FL", "georgia": "GA",
    "hawaii": "HI", "idaho": "ID", "illinois": "IL", "indiana": "IN", "iowa": "IA", "kansas": "KS",
    "kentucky": "KY", "louisiana": "LA", "maine": "ME", "maryland": "MD", "massachusetts": "MA",
    "michigan": "MI", "minnesota": "MN", "mississippi": "MS", "missouri": "MO", "montana": "MT",
    "nebraska": "NE", "nevada": "NV", "new hampshire": "NH", "new jersey": "NJ", "new mexico": "NM",
    "new york": "NY", "north carolina": "NC", "north dakota": "ND", "ohio": "OH", "oklahoma": "OK",
    "oregon": "OR", "pennsylvania": "PA", "puerto rico": "PR", "rhode island": "RI", "south carolina": "SC",
    "south dakota": "SD", "tennessee": "TN", "texas": "TX", "utah": "UT", "vermont": "VT", "virginia": "VA",
    "washington": "WA", "west virginia": "WV", "wisconsin": "WI", "wyoming": "WY",
}
US_CODES = set(US_STATES.values())


def read_jsonl(path: Path):
    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                yield json.loads(line)


def norm_time(s: str | None) -> str:
    """ISO 'YYYY-MM-DDTHH:MM:SSZ' unchanged; a Unix epoch string (some export rows use one) converted to ISO;
    anything else -> '' (such rows cannot be ordered and are dropped by the metrics)."""
    from datetime import datetime, timezone
    s = (s or "").strip()
    if re.fullmatch(r"\d{4}-\d\d-\d\dT\d\d:\d\d:\d\dZ", s):
        return s
    if re.fullmatch(r"\d{9,11}", s):
        return datetime.fromtimestamp(int(s), tz=timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    return ""


def write_json(path: Path, obj) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, indent=2, ensure_ascii=False, sort_keys=True), encoding="utf-8")


def ws(s: str) -> str:
    """Whitespace normalisation used for quote matching (and nothing else)."""
    return re.sub(r"\s+", " ", s).strip()


def digits(s: str | None) -> str:
    return re.sub(r"\D", "", s or "")


# Spelling variants of the same round item, found by listing every (family, round, item) after extraction
# (4.10). Keys and values are already lower-cased / '&' -> 'and'.
ALIASES = {
    # ISO-3 codes and short names used by the OECD cohorts
    "cze": "czech republic", "czech": "czech republic", "hun": "hungary", "pol": "poland",
    "svk": "slovak republic", "slovak": "slovak republic", "svn": "slovenia", "col": "colombia",
    "mex": "mexico", "chl": "chile", "ita": "italy",
    # NYC veterans
    "wwii": "world war ii", "gulf90s": "gulf war (1990s)", "gulf2001": "gulf war (2001-)",
    # age bands
    "85": "85 and older", "85+": "85 and older",
    # DataUSA maids
    "males 2016": "male 2016", "males in 2016": "male 2016", "f2017": "female 2017",
    # DataUSA finance gender gap
    "personal advisors": "personal financial advisors",
    "credit counselors/loan officers": "credit counselors and loan officers",
    "credit/loan": "credit counselors and loan officers",
    "insurance": "insurance sales agents", "insurance agents": "insurance sales agents",
    "csr": "customer service representatives", "customer service": "customer service representatives",
    "customer service reps": "customer service representatives",
    # DataUSA enrollment
    "msu": "michigan state university", "capella": "capella university",
}
_COUNTY = re.compile(r"^(.+?)(?: county)?,? ([a-z]{2})$")


def norm_item(item: str | None) -> str:
    s = ws(item or "").strip(" .:*`'\"").lower()
    if s.upper() in US_CODES and len(s) == 2:
        return s.upper()
    if s in US_STATES:
        return US_STATES[s]
    s = s.replace(" & ", " and ")
    m = _COUNTY.match(s)
    if m and m.group(2).upper() in US_CODES:  # 'saginaw county, mi' / 'saginaw mi' -> 'saginaw'
        s = m.group(1)
    if s.endswith(" county"):
        s = s[: -len(" county")]
    return ALIASES.get(s, s)


def item_in_quote(item: str, quote: str) -> bool:
    q = quote.lower()
    it = ws(item).lower().strip(" .:*`'\"")
    if not it:
        return False
    if it in q:
        return True
    code = norm_item(item)
    if code in US_CODES:  # 'GA' vs 'Georgia' written in the quote
        names = [n for n, c in US_STATES.items() if c == code]
        return any(n in q for n in names) or re.search(rf"\b{code.lower()}\b", q) is not None
    return False


def signature_after(text: str, quote: str) -> str | None:
    """First '-- Name' after the quote; else the last one in the text; else None."""
    t, q = ws(text), ws(quote)
    pos = t.find(q)
    if pos >= 0:
        m = SIG_RE.search(t, pos + len(q))
        if m:
            return m.group(1)
    ms = SIG_RE.findall(t)
    return ms[-1] if ms else None


def load_families() -> dict:
    return json.loads((GATE / "families.json").read_text(encoding="utf-8"))
