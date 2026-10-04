import json
import re
from pathlib import Path
import sys
import subprocess

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
    clauses = []
    for sent in re.split(r'(?<=[;\n\.])\s+', text):
        sent = sent.strip()
        if len(sent) >= 8 and sent in text:
            clauses.append(sent)

    for clause in clauses:
        for item_name, default_round, known_vals in CM_ITEMS:
            if item_name.lower() in clause.lower():
                m_item = re.search(re.escape(item_name), clause, re.IGNORECASE)
                if not m_item:
                    continue
                matched_item = m_item.group(0)

                rnd = default_round
                m_rnd = re.search(r'\bR([1-5])\b', clause, re.IGNORECASE)
                if m_rnd:
                    rnd = int(m_rnd.group(1))

                val = None
                for kv in known_vals:
                    if kv in clause:
                        val = kv
                        break
                if not val:
                    m_num = re.search(r'[\s\-=:](\d{1,2},\d{3})\b', clause)
                    if m_num:
                        val = m_num.group(1)

                q_lower = clause.lower()
                if "wrong" in q_lower or ("correct" in q_lower and "before" in q_lower):
                    kind = "answered"
                elif any(w in q_lower for w in ["expect", "project", "likely"]):
                    kind = "predicted"
                elif any(w in q_lower for w in ["answered", "confirmed", "answer ", "submitted"]):
                    kind = "answered"
                elif val is not None:
                    if any(w in q_lower for w in ["due", "schedules", "cached", "ready", "prepared"]):
                        kind = "predicted"
                    else:
                        kind = "relayed"
                else:
                    kind = "observed_prompt"

                tc = None
                m_tc = TIME_RE.search(clause)
                if m_tc:
                    tc = m_tc.group(0)

                ct = None
                m_ct = TIER_RE.search(clause)
                if m_ct:
                    ct = m_ct.group(0)

                used_cache = bool(CACHE_RE.search(clause))

                quote = clause
                if len(quote) > 380:
                    quote = quote[:380]

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
                    if not any(x["round"] == t["round"] and x["item"] == t["item"] and x["value"] == t["value"] and x["kind"] == t["kind"] for x in tuples):
                        tuples.append(t)
    
    reason = None
    if not tuples:
        if "http" in text or ("api" in text and len(tuples) == 0):
            reason = "url_or_data_dump_only"
        else:
            reason = "no_round_value_info"
            
    return reason, tuples

for b_idx in range(4, 9):
    bpath = Path(f"work/batches/datausa-cashiers-masters/datausa-cashiers-masters_{b_idx:03d}.jsonl")
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
        "batch": f"datausa-cashiers-masters/datausa-cashiers-masters_{b_idx:03d}.jsonl",
        "records": out_recs
    }

    p = Path(f"work/extract/datausa-cashiers-masters/datausa-cashiers-masters_{b_idx:03d}.json")
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(out, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"Wrote {p.name}")
    res = subprocess.run(["python", "gate/check_extract.py", str(p)], capture_output=True, text=True)
    print(res.stdout.strip())
