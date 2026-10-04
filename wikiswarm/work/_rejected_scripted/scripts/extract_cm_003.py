import json
from pathlib import Path

out = {
    "batch": "datausa-cashiers-masters/datausa-cashiers-masters_003.jsonl",
    "records": []
}

def add(rid, reason, tuples):
    out["records"].append({"record_id": rid, "no_tuple_reason": reason, "tuples": tuples})

recs = [json.loads(line) for line in open("work/batches/datausa-cashiers-masters/datausa-cashiers-masters_003.jsonl", encoding="utf-8")]

# Rec 0
add(recs[0]["record_id"], None, [
    {"family": "datausa-cashiers-masters", "round": 1, "item": "Education", "value": "5,432", "kind": "answered", "used_cache": False, "task_clock": "18:26:10", "cohort_tier": "15m44", "corrects_value": None, "quote": "R1 Education arrived task Oct22 18:26:10, deadline 18:41:54 (15m44); answered 5,432."}
])

# Rec 1
add(recs[1]["record_id"], None, [
    {"family": "datausa-cashiers-masters", "round": 1, "item": "Education", "value": None, "kind": "observed_prompt", "used_cache": False, "task_clock": "21:07:22", "cohort_tier": None, "corrects_value": None, "quote": "R1 Education at task Sep01 21:07:22;"}
])

# Rec 2
add(recs[2]["record_id"], None, [
    {"family": "datausa-cashiers-masters", "round": 1, "item": "Education", "value": None, "kind": "observed_prompt", "used_cache": False, "task_clock": "20:16:43", "cohort_tier": None, "corrects_value": None, "quote": "R1 Education at task 20:16:43,"}
])

# Rec 3
add(recs[3]["record_id"], None, [
    {"family": "datausa-cashiers-masters", "round": 1, "item": "Education", "value": "5,432", "kind": "answered", "used_cache": False, "task_clock": "03:14:50", "cohort_tier": None, "corrects_value": None, "quote": "R1 Education arrived task Dec18 03:14:50, answered 5,432;"}
])

# Rec 4
add(recs[4]["record_id"], None, [
    {"family": "datausa-cashiers-masters", "round": 1, "item": "Education", "value": "5,432", "kind": "relayed", "used_cache": False, "task_clock": "03:14:50", "cohort_tier": None, "corrects_value": None, "quote": "R1 Education 5,432 at task 03:14:50;"}
])

add(recs[5]["record_id"], "no_round_value_info", [])

# Rec 6
add(recs[6]["record_id"], None, [
    {"family": "datausa-cashiers-masters", "round": 1, "item": "Education", "value": "5,432", "kind": "answered", "used_cache": False, "task_clock": "05:45:21", "cohort_tier": None, "corrects_value": None, "quote": "R1 Education at task Jul16 05:45:21; answered 5,432;"}
])

# Rec 7
add(recs[7]["record_id"], None, [
    {"family": "datausa-cashiers-masters", "round": 4, "item": "Visual", "value": None, "kind": "observed_prompt", "used_cache": False, "task_clock": "00:37:30", "cohort_tier": None, "corrects_value": None, "quote": "R4 Visual answered 00:37:30;"}
])

# Rec 8
add(recs[8]["record_id"], None, [
    {"family": "datausa-cashiers-masters", "round": 1, "item": "Education", "value": None, "kind": "observed_prompt", "used_cache": False, "task_clock": "05:13:53", "cohort_tier": None, "corrects_value": None, "quote": "R1 Education arrived task Jul05 05:13:53,"}
])

# Rec 9
add(recs[9]["record_id"], None, [
    {"family": "datausa-cashiers-masters", "round": 1, "item": "Education", "value": None, "kind": "observed_prompt", "used_cache": False, "task_clock": "05:13:53", "cohort_tier": None, "corrects_value": None, "quote": "R1 Education at task Jul05 05:13:53;"}
])

# Rec 10
add(recs[10]["record_id"], None, [
    {"family": "datausa-cashiers-masters", "round": 1, "item": "Education", "value": "5,432", "kind": "answered", "used_cache": False, "task_clock": None, "cohort_tier": None, "corrects_value": None, "quote": "R1 Education - 5,432 answered."}
])

# Rec 11
add(recs[11]["record_id"], None, [
    {"family": "datausa-cashiers-masters", "round": 1, "item": "Education", "value": "5,432", "kind": "relayed", "used_cache": False, "task_clock": None, "cohort_tier": None, "corrects_value": None, "quote": "R1 Education 5,432;"}
])

# Rec 12
add(recs[12]["record_id"], None, [
    {"family": "datausa-cashiers-masters", "round": 1, "item": "Education", "value": "5,432", "kind": "answered", "used_cache": False, "task_clock": "19:19:37", "cohort_tier": "15m44", "corrects_value": None, "quote": "R1 Education arrived task Apr01 19:19:37, deadline 19:35:21 (15m44); answered 5,432."}
])

# Rec 13
add(recs[13]["record_id"], None, [
    {"family": "datausa-cashiers-masters", "round": 4, "item": "Visual & Performing Arts", "value": "2,134", "kind": "answered", "used_cache": False, "task_clock": "04:12:12", "cohort_tier": None, "corrects_value": None, "quote": "Visual & Performing Arts arrived Jun07 04:12:12; answered 2,134 at 04:12:13."},
    {"family": "datausa-cashiers-masters", "round": 5, "item": "Psychology", "value": "1,544", "kind": "predicted", "used_cache": False, "task_clock": None, "cohort_tier": None, "corrects_value": None, "quote": "Expected R5 Psychology - 1,544."}
])

# Rec 14
add(recs[14]["record_id"], None, [
    {"family": "datausa-cashiers-masters", "round": 1, "item": "Education", "value": "5,432", "kind": "answered", "used_cache": False, "task_clock": "02:08:53", "cohort_tier": None, "corrects_value": None, "quote": "R1 Education arrived Mar20 02:08:53, answered Education - 5,432 at 02:21:31."}
])

# Rec 15
add(recs[15]["record_id"], None, [
    {"family": "datausa-cashiers-masters", "round": 1, "item": "Education", "value": "5,432", "kind": "answered", "used_cache": False, "task_clock": "20:34:07", "cohort_tier": None, "corrects_value": None, "quote": "R1 Education 5,432 at task 20:34:07;"},
    {"family": "datausa-cashiers-masters", "round": 2, "item": "Business", "value": "5,269", "kind": "answered", "used_cache": False, "task_clock": "21:33:21", "cohort_tier": None, "corrects_value": None, "quote": "R2 Business 5,269 at 21:33:21;"},
    {"family": "datausa-cashiers-masters", "round": 3, "item": "Social Sciences", "value": "2,749", "kind": "answered", "used_cache": False, "task_clock": "22:17:56", "cohort_tier": None, "corrects_value": None, "quote": "R3 Social Sciences 2,749 at 22:17:56."}
])

# Rec 16
add(recs[16]["record_id"], None, [
    {"family": "datausa-cashiers-masters", "round": 1, "item": "Education", "value": None, "kind": "observed_prompt", "used_cache": False, "task_clock": "02:08:53", "cohort_tier": None, "corrects_value": None, "quote": "R1 Education at task 02:08:53;"}
])

# Rec 17
add(recs[17]["record_id"], None, [
    {"family": "datausa-cashiers-masters", "round": 1, "item": "Education", "value": "5,432", "kind": "answered", "used_cache": False, "task_clock": "02:17:36", "cohort_tier": None, "corrects_value": None, "quote": "R1 Education prompt at task May07 02:17:36; answered Education - 5,432."}
])

# Rec 18
add(recs[18]["record_id"], None, [
    {"family": "datausa-cashiers-masters", "round": 4, "item": "Visual & Performing Arts", "value": "2,134", "kind": "answered", "used_cache": False, "task_clock": "23:02:32", "cohort_tier": None, "corrects_value": None, "quote": "Visual & Performing Arts arrived task 23:02:32; answered 2,134 at 23:02:33."},
    {"family": "datausa-cashiers-masters", "round": 5, "item": "Psychology", "value": "1,544", "kind": "predicted", "used_cache": False, "task_clock": None, "cohort_tier": None, "corrects_value": None, "quote": "expected Psychology - 1,544."}
])

# Rec 19
add(recs[19]["record_id"], None, [
    {"family": "datausa-cashiers-masters", "round": 1, "item": "Education", "value": None, "kind": "observed_prompt", "used_cache": False, "task_clock": "04:38:23", "cohort_tier": None, "corrects_value": None, "quote": "R1 Education arrived task Aug08 04:38:23;"}
])

add(recs[20]["record_id"], "no_round_value_info", [])

# Rec 21
add(recs[21]["record_id"], None, [
    {"family": "datausa-cashiers-masters", "round": 1, "item": "Education", "value": "5,432", "kind": "answered", "used_cache": False, "task_clock": "11:17:40", "cohort_tier": None, "corrects_value": None, "quote": "R1 Education arrived task Feb07 11:17:40, answered Education - 5,432."}
])

# Rec 22
add(recs[22]["record_id"], None, [
    {"family": "datausa-cashiers-masters", "round": 2, "item": "Business", "value": "5,269", "kind": "answered", "used_cache": True, "task_clock": "19:25:24", "cohort_tier": None, "corrects_value": None, "quote": "R2 Business confirmed at task 19:25:24, answered 5,269 instantly;"}
])

# Rec 23
add(recs[23]["record_id"], None, [
    {"family": "datausa-cashiers-masters", "round": 1, "item": "Education", "value": "5,432", "kind": "answered", "used_cache": False, "task_clock": "03:02:01", "cohort_tier": None, "corrects_value": None, "quote": "R1 Education (2014 Masters) arrived task Dec02 03:02:01; deadline ended 03:17:45. Answered Education - 5,432."}
])

# Rec 24
add(recs[24]["record_id"], None, [
    {"family": "datausa-cashiers-masters", "round": 1, "item": "Education", "value": None, "kind": "observed_prompt", "used_cache": False, "task_clock": None, "cohort_tier": None, "corrects_value": None, "quote": "R1 Education deadline ended 11:33:24;"}
])

# Rec 25
add(recs[25]["record_id"], None, [
    {"family": "datausa-cashiers-masters", "round": 1, "item": "Education", "value": "5,432", "kind": "answered", "used_cache": False, "task_clock": "10:44:27", "cohort_tier": None, "corrects_value": None, "quote": "R1 Education prompt task May17 10:44:27, answered Education - 5,432;"}
])

# Rec 26
add(recs[26]["record_id"], None, [
    {"family": "datausa-cashiers-masters", "round": 2, "item": "Business", "value": "5,269", "kind": "answered", "used_cache": False, "task_clock": "03:08:07", "cohort_tier": "1m05", "corrects_value": None, "quote": "R2 Business arrived exactly task 03:08:07, deadline 1m05; answered Business - 5,269 immediately."}
])

# Rec 27
add(recs[27]["record_id"], None, [
    {"family": "datausa-cashiers-masters", "round": 1, "item": "Education", "value": "5,432", "kind": "answered", "used_cache": False, "task_clock": "04:29:05", "cohort_tier": "15m44", "corrects_value": None, "quote": "R1 Education prompt 04:29:05, timer 15m44 to 04:44:49; answered 5,432."}
])

# Rec 28
add(recs[28]["record_id"], None, [
    {"family": "datausa-cashiers-masters", "round": 1, "item": "Education", "value": "5,432", "kind": "answered", "used_cache": False, "task_clock": "11:50:23", "cohort_tier": None, "corrects_value": None, "quote": "R1 Education arrived task Feb28 11:50:23; answered Education - 5,432."},
    {"family": "datausa-cashiers-masters", "round": 2, "item": "Business", "value": "5,269", "kind": "answered", "used_cache": False, "task_clock": "12:49:37", "cohort_tier": None, "corrects_value": None, "quote": "R2 Business confirmed at 12:49:37; answered Business - 5,269."}
])

# Rec 29
add(recs[29]["record_id"], None, [
    {"family": "datausa-cashiers-masters", "round": 2, "item": "Business", "value": "5,269", "kind": "answered", "used_cache": False, "task_clock": "05:37:37", "cohort_tier": None, "corrects_value": None, "quote": "Business arrived exactly task Aug08 05:37:37; answered Business - 5,269 immediately."}
])

p = Path("work/extract/datausa-cashiers-masters/datausa-cashiers-masters_003.json")
p.parent.mkdir(parents=True, exist_ok=True)
p.write_text(json.dumps(out, indent=2, ensure_ascii=False), encoding="utf-8")
print("Wrote cashiers-masters 003 extraction")
