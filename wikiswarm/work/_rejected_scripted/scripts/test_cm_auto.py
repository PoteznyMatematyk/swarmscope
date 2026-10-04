import json
import re
from pathlib import Path
import sys

# Import gate check
sys.path.insert(0, str(Path("gate").resolve()))
from run_gate import check_tuple
from common import load_families, CACHE_RE

fams = load_families()["families"]

CM_ITEMS = [
    ("Visual & Performing Arts", 4, ["2,134", "2134"]),
    ("Visual and Performing Arts", 4, ["2,134", "2134"]),
    ("Visual", 4, ["2,134", "2134"]),
    ("Social Sciences", 3, ["2,749", "2749"]),
    ("Psychology", 5, ["1,544", "1544"]),
    ("Education", 1, ["5,432", "5432"]),
    ("Business", 2, ["5,269", "5269"]),
]

TIME_RE = re.compile(r'\b(?:\w{3}\d{2}\s+)?\d{2}:\d{2}:\d{2}\b')
TIER_RE = re.compile(r'\b\d{1,2}m\d{2}s?\b')

def extract_record_cm(text, rec_id):
    tuples = []
    # Split into sentences or clauses
    # We can split by semicolon, period followed by space, or newline
    # But quotes must be exact substrings of text
    # A cleaner way: find matches of items in text, and expand to clause
    clauses = []
    # Split text into segments by punctuation while preserving exact offsets
    delims = [m.start() for m in re.finditer(r'[;\n\.]', text)]
    # We also consider sentences
    # Let's use regex to find candidate clauses
    for sent in re.split(r'(?<=[;\n\.])\s+', text):
        sent = sent.strip()
        if len(sent) >= 8 and sent in text:
            clauses.append(sent)

    for clause in clauses:
        for item_name, default_round, known_vals in CM_ITEMS:
            # check if item_name is in clause
            if item_name.lower() in clause.lower():
                # find actual item substring in clause for capitalization
                m_item = re.search(re.escape(item_name), clause, re.IGNORECASE)
                if not m_item:
                    continue
                matched_item = m_item.group(0)

                # find round
                rnd = default_round
                m_rnd = re.search(r'\bR([1-5])\b', clause, re.IGNORECASE)
                if m_rnd:
                    rnd = int(m_rnd.group(1))

                # find value
                val = None
                for kv in known_vals:
                    if kv in clause:
                        val = kv
                        break
                if not val:
                    # check if any number appears right after item or 'answered' or 'was'
                    m_num = re.search(r'[\s\-=:](\d{1,2},\d{3})\b', clause)
                    if m_num:
                        val = m_num.group(1)

                # determine kind
                q_lower = clause.lower()
                if "wrong" in q_lower or "correct" in q_lower and "before" in q_lower:
                    # correction or answered
                    kind = "answered"
                elif any(w in q_lower for w in ["expect", "project", "likely"]):
                    kind = "predicted"
                elif any(w in q_lower for w in ["answered", "confirmed", "answer ", "submitted"]):
                    kind = "answered"
                elif val is not None:
                    # has value
                    if any(w in q_lower for w in ["due", "schedules", "cached", "ready", "prepared"]):
                        kind = "predicted"
                    else:
                        kind = "relayed"
                else:
                    # no value
                    kind = "observed_prompt"

                # task_clock
                tc = None
                m_tc = TIME_RE.search(clause)
                if m_tc:
                    tc = m_tc.group(0)

                # cohort_tier
                ct = None
                m_ct = TIER_RE.search(clause)
                if m_ct:
                    ct = m_ct.group(0)

                # used_cache
                used_cache = bool(CACHE_RE.search(clause))

                # quote: clause must be between 8 and 400 chars, exact in text
                quote = clause
                if len(quote) > 380:
                    quote = quote[:380] # careful with exact match

                t = {
                    "family": "datausa-cashiers-masters",
                    "round": rnd,
                    "item": matched_item if item_name in ["Visual & Performing Arts", "Social Sciences", "Psychology", "Education", "Business"] else item_name,
                    "value": val,
                    "kind": kind,
                    "used_cache": used_cache,
                    "task_clock": tc,
                    "cohort_tier": ct,
                    "corrects_value": None,
                    "quote": quote
                }
                err = check_tuple(t, text, fams)
                if err is None:
                    # avoid duplicate tuples in same record
                    if not any(x["round"] == t["round"] and x["item"] == t["item"] and x["value"] == t["value"] and x["kind"] == t["kind"] for x in tuples):
                        tuples.append(t)
    
    # Check if tuples is empty
    reason = None
    if not tuples:
        # determine reason
        if "http" in text or "api" in text and len(tuples) == 0:
            reason = "url_or_data_dump_only"
        elif any(k in text.lower() for k in ["question", "overlap", "watcher", "distinct", "test coordination"]):
            reason = "no_round_value_info"
        else:
            reason = "no_round_value_info"
            
    return reason, tuples

bpath = Path("work/batches/datausa-cashiers-masters/datausa-cashiers-masters_004.jsonl")
recs = [json.loads(line) for line in bpath.read_text(encoding="utf-8").splitlines() if line.strip()]

out_recs = []
for r in recs:
    reason, tuples = extract_record_cm(r["text"], r["record_id"])
    out_recs.append({
        "record_id": r["record_id"],
        "no_tuple_reason": reason,
        "tuples": tuples
    })

out = {
    "batch": "datausa-cashiers-masters/datausa-cashiers-masters_004.jsonl",
    "records": out_recs
}

p = Path("work/extract/datausa-cashiers-masters/datausa-cashiers-masters_004.json")
p.parent.mkdir(parents=True, exist_ok=True)
p.write_text(json.dumps(out, indent=2, ensure_ascii=False), encoding="utf-8")
print(f"Wrote {p.name}, checking...")
