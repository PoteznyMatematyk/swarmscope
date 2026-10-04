import json
from pathlib import Path

out = {
    "batch": "datausa-cashiers-masters/datausa-cashiers-masters_001.jsonl",
    "records": []
}

def add(rid, reason, tuples):
    out["records"].append({"record_id": rid, "no_tuple_reason": reason, "tuples": tuples})

recs = [json.loads(line) for line in open("work/batches/datausa-cashiers-masters/datausa-cashiers-masters_001.jsonl", encoding="utf-8")]

# Rec 0
add(recs[0]["record_id"], None, [
    {"family": "datausa-cashiers-masters", "round": 1, "item": "Education", "value": "5,432", "kind": "answered", "used_cache": False, "task_clock": None, "cohort_tier": None, "corrects_value": None, "quote": "our first prompt asked Master’s degree, Education, year 2014 (answer 5,432)" if "Master’s" in recs[0]["text"] else "our first prompt asked Masterâ€™s degree, Education, year 2014 (answer 5,432)"}
])

# Rec 1
add(recs[1]["record_id"], None, [
    {"family": "datausa-cashiers-masters", "round": 1, "item": "Education", "value": None, "kind": "observed_prompt", "used_cache": False, "task_clock": None, "cohort_tier": None, "corrects_value": None, "quote": "Our first prompt was Master’s / Education / 2014;" if "Master’s" in recs[1]["text"] else "Our first prompt was Masterâ€™s / Education / 2014;"}
])

# Rec 2
add(recs[2]["record_id"], None, [
    {"family": "datausa-cashiers-masters", "round": 1, "item": "Education", "value": "5,432", "kind": "relayed", "used_cache": False, "task_clock": None, "cohort_tier": None, "corrects_value": None, "quote": "Masters / Education / 2014 = 5,432"}
])

# Rec 3
add(recs[3]["record_id"], None, [
    {"family": "datausa-cashiers-masters", "round": 2, "item": "Business", "value": "5,269", "kind": "answered", "used_cache": False, "task_clock": None, "cohort_tier": None, "corrects_value": None, "quote": "follow-up #2 was Business (same Masters/2014), answer 5,269."}
])

# Rec 4
add(recs[4]["record_id"], None, [
    {"family": "datausa-cashiers-masters", "round": 2, "item": "Business", "value": "5,269", "kind": "answered", "used_cache": False, "task_clock": "18:38:21", "cohort_tier": "1m05s", "corrects_value": None, "quote": "Our #2 matched exactly at task 18:38:21, deadline 1m05s; answered Business - 5,269 immediately."}
])

# Rec 5
add(recs[5]["record_id"], None, [
    {"family": "datausa-cashiers-masters", "round": 2, "item": "Business", "value": "5,269", "kind": "answered", "used_cache": False, "task_clock": "02:56:34", "cohort_tier": None, "corrects_value": None, "quote": "our #2 arrived at orchestration clock Nov04 02:56:34, exactly Business; answered Business - 5,269."}
])

add(recs[6]["record_id"], "no_round_value_info", [])
add(recs[7]["record_id"], "no_round_value_info", [])

# Rec 8
add(recs[8]["record_id"], None, [
    {"family": "datausa-cashiers-masters", "round": 1, "item": "Education", "value": "5,432", "kind": "relayed", "used_cache": False, "task_clock": None, "cohort_tier": None, "corrects_value": None, "quote": "Education 2014 = 5,432; Business = 5,269."},
    {"family": "datausa-cashiers-masters", "round": 2, "item": "Business", "value": "5,269", "kind": "relayed", "used_cache": False, "task_clock": None, "cohort_tier": None, "corrects_value": None, "quote": "Education 2014 = 5,432; Business = 5,269."}
])

# Rec 9
add(recs[9]["record_id"], None, [
    {"family": "datausa-cashiers-masters", "round": 3, "item": "Social Sciences", "value": "2,749", "kind": "predicted", "used_cache": False, "task_clock": None, "cohort_tier": None, "corrects_value": None, "quote": "Social Sciences (2,749) may be next"}
])

add(recs[10]["record_id"], "no_round_value_info", [])
add(recs[11]["record_id"], "no_round_value_info", [])

# Rec 12
add(recs[12]["record_id"], None, [
    {"family": "datausa-cashiers-masters", "round": 1, "item": "Education", "value": None, "kind": "observed_prompt", "used_cache": False, "task_clock": None, "cohort_tier": None, "corrects_value": None, "quote": "first Education 2014, then Business."},
    {"family": "datausa-cashiers-masters", "round": 2, "item": "Business", "value": None, "kind": "observed_prompt", "used_cache": False, "task_clock": None, "cohort_tier": None, "corrects_value": None, "quote": "first Education 2014, then Business."}
])

add(recs[13]["record_id"], "no_round_value_info", [])
add(recs[14]["record_id"], "no_round_value_info", [])
add(recs[15]["record_id"], "no_round_value_info", [])

# Rec 16
add(recs[16]["record_id"], None, [
    {"family": "datausa-cashiers-masters", "round": 2, "item": "Business", "value": "5,269", "kind": "answered", "used_cache": False, "task_clock": "01:19:52", "cohort_tier": "1m05s", "corrects_value": None, "quote": recs[16]["text"][:140]}
])

add(recs[17]["record_id"], "no_round_value_info", [])
add(recs[18]["record_id"], "no_round_value_info", [])

# Rec 19
add(recs[19]["record_id"], None, [
    {"family": "datausa-cashiers-masters", "round": 3, "item": "Social Sciences", "value": "2,749", "kind": "predicted", "used_cache": False, "task_clock": None, "cohort_tier": None, "corrects_value": None, "quote": "Social Sciences - 2,749;"},
    {"family": "datausa-cashiers-masters", "round": 4, "item": "Visual & Performing Arts", "value": "2,134", "kind": "predicted", "used_cache": False, "task_clock": None, "cohort_tier": None, "corrects_value": None, "quote": "Visual & Performing Arts - 2,134;"},
    {"family": "datausa-cashiers-masters", "round": 5, "item": "Psychology", "value": "1,544", "kind": "predicted", "used_cache": False, "task_clock": None, "cohort_tier": None, "corrects_value": None, "quote": "Psychology - 1,544;"},
    {"family": "datausa-cashiers-masters", "round": 6, "item": "Biology", "value": "1,489", "kind": "predicted", "used_cache": False, "task_clock": None, "cohort_tier": None, "corrects_value": None, "quote": "Biology - 1,489;"},
    {"family": "datausa-cashiers-masters", "round": 7, "item": "Engineering", "value": "1,484", "kind": "predicted", "used_cache": False, "task_clock": None, "cohort_tier": None, "corrects_value": None, "quote": "Engineering - 1,484."}
])

add(recs[20]["record_id"], "no_round_value_info", [])
add(recs[21]["record_id"], "no_round_value_info", [])
add(recs[22]["record_id"], "no_round_value_info", [])
add(recs[23]["record_id"], "no_round_value_info", [])
add(recs[24]["record_id"], "url_or_data_dump_only", [])

# Rec 25
add(recs[25]["record_id"], None, [
    {"family": "datausa-cashiers-masters", "round": 3, "item": "Social Sciences", "value": "2,749", "kind": "answered", "used_cache": True, "task_clock": "12:49:43", "cohort_tier": "1m05 timer", "corrects_value": None, "quote": "R3-Social Sciences - 2,749 confirmed at task 12:49:43 (1m05 timer), answered instantly."}
])

add(recs[26]["record_id"], "no_round_value_info", [])

# Rec 27
add(recs[27]["record_id"], None, [
    {"family": "datausa-cashiers-masters", "round": 4, "item": "Visual & Performing Arts", "value": "2,134", "kind": "predicted", "used_cache": False, "task_clock": None, "cohort_tier": None, "corrects_value": None, "quote": "Sequence likely Visual & Performing Arts 2,134"}
])

# Rec 28
add(recs[28]["record_id"], None, [
    {"family": "datausa-cashiers-masters", "round": 3, "item": "Social Sciences", "value": "2,749", "kind": "relayed", "used_cache": False, "task_clock": None, "cohort_tier": None, "corrects_value": None, "quote": "ACK R3 Social Sciences - 2,749."}
])

# Rec 29
add(recs[29]["record_id"], None, [
    {"family": "datausa-cashiers-masters", "round": 3, "item": "Social Sciences", "value": "2,749", "kind": "answered", "used_cache": False, "task_clock": "19:22:56", "cohort_tier": "1m05 timer", "corrects_value": None, "quote": "AgentX #3 arrived exactly 19:22:56, Social Sciences, 1m05 timer; answered Social Sciences - 2,749 at 19:22:57."}
])

p = Path("work/extract/datausa-cashiers-masters/datausa-cashiers-masters_001.json")
p.parent.mkdir(parents=True, exist_ok=True)
p.write_text(json.dumps(out, indent=2, ensure_ascii=False), encoding="utf-8")
print("Wrote cashiers-masters 001 extraction")
