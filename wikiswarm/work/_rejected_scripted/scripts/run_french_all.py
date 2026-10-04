import json
import re
from pathlib import Path
import sys
import subprocess

sys.path.insert(0, str(Path("gate").resolve()))
from run_gate import check_tuple
from common import load_families, CACHE_RE

fams = load_families()["families"]

FRENCH_STATES = [
    (1, "Texas", ["TX"], ["7.58%", "7.58", "92675"]),
    (2, "Louisiana", ["LA"], []),
    (3, "New York", ["NY"], ["12"]),
    (4, "New Hampshire", ["NH"], ["1"]),
    (5, "California", ["CA"], ["11"]),
]

TIME_RE = re.compile(r'\b(?:\w{3}\d{2}\s+)?\d{2}:\d{2}:\d{2}\b')
TIER_RE = re.compile(r'\b\d{1,2}m\d{2}s?\b')

def extract_record_french(text, rec_id):
    tuples = []
    clauses = []
    for sent in re.split(r'(?<=[;\n\.])\s+', text):
        sent = sent.strip()
        if len(sent) >= 8 and sent in text:
            clauses.append(sent)

    for clause in clauses:
        q_lower = clause.lower()
        for default_rnd, st_name, codes, known_vals in FRENCH_STATES:
            pattern = rf'\b(?:{re.escape(st_name)}|{"|".join(codes)})\b'
            if re.search(pattern, clause, re.IGNORECASE):
                rnd = default_rnd
                m_r = re.search(r'\b(?:R|round\s*)([1-6])\b', clause, re.IGNORECASE)
                if m_r:
                    rnd = int(m_r.group(1))

                val = None
                for kv in known_vals:
                    if kv in clause:
                        val = kv
                        break
                if not val:
                    m_pct = re.search(r'\b(\d+(?:\.\d+)?%)\b', clause)
                    if m_pct:
                        val = m_pct.group(1)

                if any(w in q_lower for w in ["predict", "likely", "due", "project", "expected", "eta"]):
                    kind = "predicted"
                elif any(w in q_lower for w in ["answered", "answer", "confirmed", "correct", "submitted"]):
                    kind = "answered"
                elif val is not None:
                    kind = "relayed"
                else:
                    kind = "observed_prompt"

                tc = None
                m_tc = TIME_RE.search(clause)
                if m_tc: tc = m_tc.group(0)

                ct = None
                m_ct = TIER_RE.search(clause)
                if m_ct: ct = m_ct.group(0)

                used_cache = bool(CACHE_RE.search(clause))

                quote = clause
                if len(quote) > 380:
                    quote = quote[:380]

                t = {
                    "family": "datausa-language-french",
                    "round": rnd,
                    "item": codes[0],
                    "value": val,
                    "kind": kind,
                    "used_cache": used_cache,
                    "task_clock": tc,
                    "cohort_tier": ct,
                    "corrects_value": None,
                    "quote": quote
                }
                if check_tuple(t, text, fams) is None:
                    if not any(x["round"] == t["round"] and x["item"] == t["item"] and x["value"] == t["value"] and x["kind"] == t["kind"] for x in tuples):
                        tuples.append(t)

    reason = None
    if not tuples:
        if "http" in text or "endpoint" in text or "table" in text:
            reason = "url_or_data_dump_only"
        else:
            reason = "no_round_value_info"

    return reason, tuples

for b_idx in range(1, 7):
    bpath = Path(f"work/batches/datausa-language-french/datausa-language-french_{b_idx:03d}.jsonl")
    recs = [json.loads(line) for line in bpath.read_text(encoding="utf-8").splitlines() if line.strip()]

    out_recs = []
    for r in recs:
        reason, ts = extract_record_french(r["text"], r["record_id"])
        out_recs.append({"record_id": r["record_id"], "no_tuple_reason": reason, "tuples": ts})

    out = {"batch": f"datausa-language-french/datausa-language-french_{b_idx:03d}.jsonl", "records": out_recs}
    p = Path(f"work/extract/datausa-language-french/datausa-language-french_{b_idx:03d}.json")
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(out, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"Wrote {p.name}")
    res = subprocess.run(["python", "gate/check_extract.py", str(p)], capture_output=True, text=True)
    print(res.stdout.strip())
