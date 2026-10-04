import json
import re
from pathlib import Path
import sys

sys.path.insert(0, str(Path("gate").resolve()))
from run_gate import check_tuple
from common import load_families, CACHE_RE, US_STATES

fams = load_families()["families"]

SECTOR_STATES = [
    (1, "Massachusetts", ["MA"]),
    (2, "Connecticut", ["CT"]),
    (3, "Michigan", ["MI"]),
    (4, "West Virginia", ["WV"]),
    (5, "New Hampshire", ["NH"]),
    (5, "Idaho", ["ID"]),
]

TIME_RE = re.compile(r'\b(?:\w{3}\d{2}\s+)?\d{2}:\d{2}:\d{2}\b')
TIER_RE = re.compile(r'\b\d{1,2}m\d{2}s?\b')

def extract_record_sector61(text, rec_id):
    tuples = []
    clauses = []
    for sent in re.split(r'(?<=[;\n\.])\s+', text):
        sent = sent.strip()
        if len(sent) >= 8 and sent in text:
            clauses.append(sent)

    # Check for arrow sequence "Massachusetts -> Connecticut -> Michigan -> West Virginia"
    # or general sentence mentioning states
    for clause in clauses:
        q_lower = clause.lower()
        # If arrow sequence in clause
        if "->" in clause:
            # e.g. "Massachusetts -> Connecticut -> Michigan -> West Virginia"
            # find all states in clause
            for default_round, state_name, codes in SECTOR_STATES:
                if state_name.lower() in q_lower or any(re.search(rf'\b{c.lower()}\b', q_lower) for c in codes):
                    rnd = default_round
                    # check if explicit round given
                    m_r = re.search(rf'\b(?:R|STATE\s*)([1-5])\b', clause, re.IGNORECASE)
                    # For sequence with arrows, we can infer round from position if not given
                    # But default_round is already accurate (MA=1, CT=2, MI=3, WV=4)
                    kind = "observed_prompt" if "observed" in q_lower or "arrived" in q_lower or "prompt" in q_lower else "relayed"
                    tc = None
                    m_tc = TIME_RE.search(clause)
                    if m_tc: tc = m_tc.group(0)
                    ct = None
                    m_ct = TIER_RE.search(clause)
                    if m_ct: ct = m_ct.group(0)
                    used_cache = bool(CACHE_RE.search(clause))

                    # find item text
                    item = codes[0] # or state_name

                    t = {
                        "family": "datausa-sector61-state",
                        "round": rnd,
                        "item": item,
                        "value": None,
                        "kind": kind,
                        "used_cache": used_cache,
                        "task_clock": tc,
                        "cohort_tier": ct,
                        "corrects_value": None,
                        "quote": clause
                    }
                    if check_tuple(t, text, fams) is None:
                        if not any(x["round"] == t["round"] and x["item"] == t["item"] for x in tuples):
                            tuples.append(t)
        else:
            # non-arrow clauses
            for default_round, state_name, codes in SECTOR_STATES:
                pattern = rf'\b(?:{re.escape(state_name)}|{"|".join(codes)})\b'
                if re.search(pattern, clause, re.IGNORECASE):
                    rnd = default_round
                    m_r = re.search(r'\b(?:R|round\s*|STATE\s*)([1-5])\b', clause, re.IGNORECASE)
                    if m_r:
                        rnd = int(m_r.group(1))

                    if any(w in q_lower for w in ["predict", "likely", "due", "project"]):
                        kind = "predicted"
                    elif any(w in q_lower for w in ["answered", "answer", "confirmed", "exact"]):
                        kind = "answered"
                    elif any(w in q_lower for w in ["arrived", "prompt", "observed"]):
                        kind = "observed_prompt"
                    else:
                        kind = "relayed"

                    tc = None
                    m_tc = TIME_RE.search(clause)
                    if m_tc: tc = m_tc.group(0)
                    ct = None
                    m_ct = TIER_RE.search(clause)
                    if m_ct: ct = m_ct.group(0)
                    used_cache = bool(CACHE_RE.search(clause))

                    item = codes[0]

                    # check if value is given (single number or None)
                    # for sector61, value is usually None unless single number
                    val = None
                    m_val = re.search(r'answer\s+(\d{6,7})\b', clause)
                    if m_val:
                        val = m_val.group(1)

                    t = {
                        "family": "datausa-sector61-state",
                        "round": rnd,
                        "item": item,
                        "value": val,
                        "kind": kind,
                        "used_cache": used_cache,
                        "task_clock": tc,
                        "cohort_tier": ct,
                        "corrects_value": None,
                        "quote": clause
                    }
                    if check_tuple(t, text, fams) is None:
                        if not any(x["round"] == t["round"] and x["item"] == t["item"] for x in tuples):
                            tuples.append(t)

    reason = None
    if not tuples:
        reason = "no_round_value_info"

    return reason, tuples

bpath = Path("work/batches/datausa-sector61-state/datausa-sector61-state_001.jsonl")
recs = [json.loads(line) for line in bpath.read_text(encoding="utf-8").splitlines() if line.strip()]
out_recs = []
for r in recs:
    reason, ts = extract_record_sector61(r["text"], r["record_id"])
    out_recs.append({"record_id": r["record_id"], "no_tuple_reason": reason, "tuples": ts})

out = {"batch": "datausa-sector61-state/datausa-sector61-state_001.jsonl", "records": out_recs}
p = Path("work/extract/datausa-sector61-state/datausa-sector61-state_001.json")
p.parent.mkdir(parents=True, exist_ok=True)
p.write_text(json.dumps(out, indent=2, ensure_ascii=False), encoding="utf-8")
print("Wrote sector61 001")
