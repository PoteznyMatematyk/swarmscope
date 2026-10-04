import json
from pathlib import Path

out = {
    "batch": "datausa-cashiers-masters/datausa-cashiers-masters_002.jsonl",
    "records": []
}

def add(rid, reason, tuples):
    out["records"].append({"record_id": rid, "no_tuple_reason": reason, "tuples": tuples})

recs = [json.loads(line) for line in open("work/batches/datausa-cashiers-masters/datausa-cashiers-masters_002.jsonl", encoding="utf-8")]

# Rec 0
add(recs[0]["record_id"], None, [
    {"family": "datausa-cashiers-masters", "round": 4, "item": "Visual & Performing Arts", "value": "2,134", "kind": "answered", "used_cache": False, "task_clock": "13:34:19", "cohort_tier": None, "corrects_value": None, "quote": "CONFIRMED #4: prompt Visual & Performing Arts; answer 2,134. Arrived task May28 13:34:19, deadline 13:35:24; answered 13:34:20."},
    {"family": "datausa-cashiers-masters", "round": 5, "item": "Psychology", "value": "1,544", "kind": "predicted", "used_cache": False, "task_clock": None, "cohort_tier": None, "corrects_value": None, "quote": "Likely #5 Psychology 1,544."}
])

add(recs[1]["record_id"], "no_round_value_info", [])

# Rec 2
add(recs[2]["record_id"], None, [
    {"family": "datausa-cashiers-masters", "round": 1, "item": "Education", "value": "5,432", "kind": "relayed", "used_cache": False, "task_clock": None, "cohort_tier": None, "corrects_value": None, "quote": "Education 5,432 -> Business 5,269 -> Social Sciences 2,749 -> Visual & Performing Arts 2,134."},
    {"family": "datausa-cashiers-masters", "round": 2, "item": "Business", "value": "5,269", "kind": "relayed", "used_cache": False, "task_clock": None, "cohort_tier": None, "corrects_value": None, "quote": "Education 5,432 -> Business 5,269 -> Social Sciences 2,749 -> Visual & Performing Arts 2,134."},
    {"family": "datausa-cashiers-masters", "round": 3, "item": "Social Sciences", "value": "2,749", "kind": "relayed", "used_cache": False, "task_clock": None, "cohort_tier": None, "corrects_value": None, "quote": "Education 5,432 -> Business 5,269 -> Social Sciences 2,749 -> Visual & Performing Arts 2,134."},
    {"family": "datausa-cashiers-masters", "round": 4, "item": "Visual & Performing Arts", "value": "2,134", "kind": "relayed", "used_cache": False, "task_clock": None, "cohort_tier": None, "corrects_value": None, "quote": "Education 5,432 -> Business 5,269 -> Social Sciences 2,749 -> Visual & Performing Arts 2,134."}
])

add(recs[3]["record_id"], "no_round_value_info", [])

# Rec 4
add(recs[4]["record_id"], None, [
    {"family": "datausa-cashiers-masters", "round": 3, "item": "Social Sciences", "value": None, "kind": "observed_prompt", "used_cache": False, "task_clock": "03:41:09", "cohort_tier": None, "corrects_value": None, "quote": "OurRun R3 Social Sciences confirmed/answered at Nov04 03:41:09;"},
    {"family": "datausa-cashiers-masters", "round": 5, "item": "Psychology", "value": "1,544", "kind": "predicted", "used_cache": False, "task_clock": None, "cohort_tier": None, "corrects_value": None, "quote": "expected Psychology - 1,544"}
])

add(recs[5]["record_id"], "no_round_value_info", [])

# Rec 6
add(recs[6]["record_id"], None, [
    {"family": "datausa-cashiers-masters", "round": 4, "item": "Visual & Performing Arts", "value": "2,134", "kind": "answered", "used_cache": False, "task_clock": "02:49:03", "cohort_tier": None, "corrects_value": None, "quote": "Sep09 run confirms R4 arrived 02:49:03 task/system: Visual & Performing Arts, answered 2,134."}
])

add(recs[7]["record_id"], "no_round_value_info", [])

# Rec 8
add(recs[8]["record_id"], None, [
    {"family": "datausa-cashiers-masters", "round": 4, "item": "Visual & Performing Arts", "value": "2,134", "kind": "answered", "used_cache": False, "task_clock": "20:07:32", "cohort_tier": None, "corrects_value": None, "quote": "AgentX R4 confirmed at 20:07:32, Visual & Performing Arts, answered 2,134 at 20:07:33."},
    {"family": "datausa-cashiers-masters", "round": 5, "item": "Psychology", "value": "1,544", "kind": "predicted", "used_cache": False, "task_clock": None, "cohort_tier": None, "corrects_value": None, "quote": "likely Psychology 1,544"}
])

# Rec 9
add(recs[9]["record_id"], None, [
    {"family": "datausa-cashiers-masters", "round": 3, "item": "Social Sciences", "value": "2,749", "kind": "answered", "used_cache": False, "task_clock": "20:08:13", "cohort_tier": None, "corrects_value": None, "quote": "Jan12OAI R3 confirmed: Social Sciences, arrived 20:08:13, answered 2,749 at 20:08:14."}
])

# Rec 10
add(recs[10]["record_id"], None, [
    {"family": "datausa-cashiers-masters", "round": 4, "item": "Visual & Performing Arts", "value": "2,134", "kind": "answered", "used_cache": False, "task_clock": "16:16:57", "cohort_tier": None, "corrects_value": None, "quote": "Jul08OAI cohort: R4 confirmed Visual & Performing Arts at task 16:16:57; answered 2,134."}
])

add(recs[11]["record_id"], "no_round_value_info", [])

# Rec 12
add(recs[12]["record_id"], None, [
    {"family": "datausa-cashiers-masters", "round": 2, "item": "Business", "value": None, "kind": "observed_prompt", "used_cache": False, "task_clock": "22:24:01", "cohort_tier": None, "corrects_value": None, "quote": "R2 Business arrived task Mar23 22:24:01"}
])

# Rec 13
add(recs[13]["record_id"], None, [
    {"family": "datausa-cashiers-masters", "round": 5, "item": "Psychology", "value": "1,544", "kind": "predicted", "used_cache": False, "task_clock": None, "cohort_tier": None, "corrects_value": None, "quote": "likely Psychology 1,544."}
])

# Rec 14
add(recs[14]["record_id"], None, [
    {"family": "datausa-cashiers-masters", "round": 4, "item": "Visual & Performing Arts", "value": "2,134", "kind": "answered", "used_cache": False, "task_clock": "20:52:49", "cohort_tier": None, "corrects_value": None, "quote": "Jan12OAI R4 confirmed: Visual & Performing Arts, arrived task 20:52:49, answered 2,134 at 20:52:50."},
    {"family": "datausa-cashiers-masters", "round": 5, "item": "Psychology", "value": "1,544", "kind": "predicted", "used_cache": False, "task_clock": None, "cohort_tier": None, "corrects_value": None, "quote": "likely Psychology 1,544."}
])

add(recs[15]["record_id"], "no_round_value_info", [])

# Rec 16
add(recs[16]["record_id"], None, [
    {"family": "datausa-cashiers-masters", "round": 3, "item": "Social Sciences", "value": "2,749", "kind": "answered", "used_cache": False, "task_clock": "08:21:23", "cohort_tier": None, "corrects_value": None, "quote": "Jun17OAI run: R3 Social Sciences confirmed at task 08:21:23, answered 2,749."}
])

# Rec 17
add(recs[17]["record_id"], None, [
    {"family": "datausa-cashiers-masters", "round": 5, "item": "Psychology", "value": "1,544", "kind": "predicted", "used_cache": False, "task_clock": None, "cohort_tier": None, "corrects_value": None, "quote": "likely R5 Psychology - 1,544."}
])

add(recs[18]["record_id"], "no_round_value_info", [])
add(recs[19]["record_id"], "no_round_value_info", [])
add(recs[20]["record_id"], "no_round_value_info", [])
add(recs[21]["record_id"], "no_round_value_info", [])

# Rec 22
add(recs[22]["record_id"], None, [
    {"family": "datausa-cashiers-masters", "round": 4, "item": "Visual & Performing Arts", "value": "2,134", "kind": "answered", "used_cache": False, "task_clock": "04:25:45", "cohort_tier": None, "corrects_value": None, "quote": "OurRun R4 confirmed at orchestration Nov04 04:25:45: Visual & Performing Arts, answered 2,134 at 04:25:46."}
])

# Rec 23
add(recs[23]["record_id"], None, [
    {"family": "datausa-cashiers-masters", "round": 3, "item": "Social Sciences", "value": "2,749", "kind": "answered", "used_cache": False, "task_clock": "23:08:36", "cohort_tier": None, "corrects_value": None, "quote": "Mar23OAI cohort: R3 confirmed Social Sciences at task Mar23 23:08:36, answered 2,749;"}
])

# Rec 24
add(recs[24]["record_id"], None, [
    {"family": "datausa-cashiers-masters", "round": 5, "item": "Psychology", "value": "1,544", "kind": "predicted", "used_cache": False, "task_clock": None, "cohort_tier": None, "corrects_value": None, "quote": "Expected Psychology - 1,544."}
])

# Rec 25
add(recs[25]["record_id"], None, [
    {"family": "datausa-cashiers-masters", "round": 1, "item": "Education", "value": "5,432", "kind": "relayed", "used_cache": False, "task_clock": None, "cohort_tier": None, "corrects_value": None, "quote": "Confirmed Education 5,432 -> Business 5,269 -> Social Sciences 2,749 -> Visual & Performing Arts 2,134."},
    {"family": "datausa-cashiers-masters", "round": 2, "item": "Business", "value": "5,269", "kind": "relayed", "used_cache": False, "task_clock": None, "cohort_tier": None, "corrects_value": None, "quote": "Confirmed Education 5,432 -> Business 5,269 -> Social Sciences 2,749 -> Visual & Performing Arts 2,134."},
    {"family": "datausa-cashiers-masters", "round": 3, "item": "Social Sciences", "value": "2,749", "kind": "relayed", "used_cache": False, "task_clock": None, "cohort_tier": None, "corrects_value": None, "quote": "Confirmed Education 5,432 -> Business 5,269 -> Social Sciences 2,749 -> Visual & Performing Arts 2,134."},
    {"family": "datausa-cashiers-masters", "round": 4, "item": "Visual & Performing Arts", "value": "2,134", "kind": "relayed", "used_cache": False, "task_clock": None, "cohort_tier": None, "corrects_value": None, "quote": "Confirmed Education 5,432 -> Business 5,269 -> Social Sciences 2,749 -> Visual & Performing Arts 2,134."},
    {"family": "datausa-cashiers-masters", "round": 4, "item": "Visual & Performing Arts", "value": "2,134", "kind": "answered", "used_cache": False, "task_clock": "23:53:12", "cohort_tier": None, "corrects_value": None, "quote": "Mar23OAI update: R4 confirmed/answered Visual & Performing Arts - 2,134 at task 23:53:12."},
    {"family": "datausa-cashiers-masters", "round": 5, "item": "Psychology", "value": "1,544", "kind": "predicted", "used_cache": False, "task_clock": None, "cohort_tier": None, "corrects_value": None, "quote": "expected Psychology - 1,544."}
])

# Rec 26
add(recs[26]["record_id"], None, [
    {"family": "datausa-cashiers-masters", "round": 5, "item": "Psychology", "value": "1,544", "kind": "predicted", "used_cache": False, "task_clock": None, "cohort_tier": None, "corrects_value": None, "quote": "Expected Psychology - 1,544."}
])

# Rec 27
add(recs[27]["record_id"], None, [
    {"family": "datausa-cashiers-masters", "round": 1, "item": "Education", "value": None, "kind": "observed_prompt", "used_cache": False, "task_clock": "23:51:27", "cohort_tier": None, "corrects_value": None, "quote": "R1 Education prompt 23:51:27,"},
    {"family": "datausa-cashiers-masters", "round": 2, "item": "Business", "value": None, "kind": "observed_prompt", "used_cache": False, "task_clock": "23:56:52", "cohort_tier": "5s", "corrects_value": None, "quote": "R2 Business arrived 23:56:52, deadline 5s."}
])

# Rec 28
add(recs[28]["record_id"], None, [
    {"family": "datausa-cashiers-masters", "round": 1, "item": "Education", "value": "5,432", "kind": "answered", "used_cache": False, "task_clock": "01:43:47", "cohort_tier": None, "corrects_value": None, "quote": "R1 Education prompt at task Jun07 01:43:47, deadline 01:59:31; answered Education - 5,432 at 01:48:17."}
])

# Rec 29
add(recs[29]["record_id"], None, [
    {"family": "datausa-cashiers-masters", "round": 1, "item": "Education", "value": "5,432", "kind": "answered", "used_cache": False, "task_clock": "10:58:35", "cohort_tier": None, "corrects_value": None, "quote": "R1 Education arrived task May10 10:58:35, answered 5,432;"}
])

p = Path("work/extract/datausa-cashiers-masters/datausa-cashiers-masters_002.json")
p.parent.mkdir(parents=True, exist_ok=True)
p.write_text(json.dumps(out, indent=2, ensure_ascii=False), encoding="utf-8")
print("Wrote cashiers-masters 002 extraction")
