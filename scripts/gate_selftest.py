"""Self-test of accept_packet.py: one honest packet (must ACCEPT) and adversarial 'lazy worker' mutations (must NOT).

    python scripts/gate_selftest.py <scratch dir>

Needs the AI Village work files (data/work: windows, snapshot, runs/pilot) - it builds candidate packets from the pilot claims of chunk E1_leader_c01.
It briefly edits packets/tripwire.json (M10) and restores it: never run it while analysts or a workflow are running.
"""
import json
import re
import shutil
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
WORK = ROOT / "data" / "work"
PY = sys.executable
GATE = str(Path(__file__).resolve().parent / "accept_packet.py")
SCR = Path(sys.argv[1])
sys.path.insert(0, str(WORK / "tool"))
from swarmscope.claims import verify_claims  # noqa: E402
from swarmscope.store import Store  # noqa: E402

store = Store(WORK / "snapshot.duckdb", read_only=True)
CHUNK = WORK / "windows" / "E1_leader" / "chunk_01.txt"
LENS_Q = {"structure": ["Q1", "Q2", "Q3", "Q7", "Q10"], "friction": ["Q4", "Q5", "Q6", "Q8", "Q9", "Q11"]}
EV = re.compile(r"^\[[^\]]+\] .{0,240}?\{([0-9a-f]{10})\}: ")
lines = CHUNK.read_text(encoding="utf-8").splitlines()
evlines = [(i + 1, EV.match(l).group(1)) for i, l in enumerate(lines) if EV.match(l)]
pilot = {"structure": WORK / "runs/pilot/E1_c01_structure", "friction": WORK / "runs/pilot/E1_c01_friction"}


def dump(p, obj):
    p.write_text(json.dumps(obj, indent=1, ensure_ascii=False), encoding="utf-8")
    time.sleep(0.05)


def make_receipts(path, false=False):
    out = []
    for k in range(0, len(evlines), 100):
        seg = evlines[k:k + 100]
        pick = seg[:2] if not false else evlines[-2:]  # false receipt: handles from the END of the chunk
        out.append({"slice": k // 100 + 1, "lines": [seg[0][0], seg[-1][0]], "refs": [r for _, r in pick], "gist": "slice summary"})
    path.write_text("\n".join(json.dumps(o) for o in out) + "\n", encoding="utf-8")


def build(name, transform=None, receipts="ok"):
    d = SCR / name
    shutil.rmtree(d, ignore_errors=True)
    d.mkdir(parents=True)
    for lens, src in pilot.items():
        ld = d / lens
        ld.mkdir()
        claims = json.loads((src / "claims_v2.json").read_text(encoding="utf-8"))
        claims["chunk"] = str(CHUNK).replace("\\", "/")
        for i, c in enumerate(claims["claims"]):
            c["importance"] = 2 + (i % 4)
            c.pop("first_ts", None)
        answered = {c["question"] for c in claims["claims"]}
        claims["unanswered"] = {q: "no supporting events for this question in this chunk" for q in LENS_Q[lens] if q not in answered}
        v1 = json.loads(json.dumps(claims))
        dump(ld / "claims_v1.json", v1)
        dump(ld / "verified_v1.json", verify_claims(store, v1))
        v2 = json.loads(json.dumps(claims))
        chg = []
        if transform:
            v2, chg = transform(lens, v2)
        dump(ld / "claims_v2.json", v2)
        dump(ld / "v2_changes.json", chg)
        dump(ld / "verified_v2.json", verify_claims(store, v2))
    if receipts == "ok":
        make_receipts(d / "reading_log.jsonl")
    elif receipts == "false":
        make_receipts(d / "reading_log.jsonl", false=True)
    return d


def run(d):
    r = subprocess.run([PY, GATE, str(d), "--chunk", str(CHUNK)], capture_output=True, text=True, encoding="utf-8")
    try:
        j = json.loads(r.stdout)
    except Exception:
        return {"verdict": "CRASH", "fails": [r.stderr[-300:]]}
    return j


def show(name, j, expect):
    ok = (j["verdict"] == "ACCEPT") if expect == "ACCEPT" else (j["verdict"] != "ACCEPT")
    print(f"[{'PASS' if ok else 'FAIL'}] {name:<28} -> {j['verdict']:<7} (expected {expect})")
    for f in j.get("fails", [])[:3]:
        print("        -", f[:170])


# ---- mutations
def m_short_quotes(lens, v2):
    for c in v2["claims"]:
        for e in c["evidence"]:
            e["quote"] = " ".join(e["quote"].split()[:3])
    return v2, []


def m_shallow(lens, v2):
    cut = evlines[len(evlines) // 4][1]
    early = {r for _, r in evlines[: len(evlines) // 4]}
    v2["claims"] = [c for c in v2["claims"] if all(e["ref"] in early for e in c["evidence"])]
    return v2, []


def m_delete(lens, v2):
    v2["claims"] = v2["claims"][: len(v2["claims"]) // 2]
    return v2, []  # deleted, not logged


def m_bad_quote(lens, v2):
    v2["claims"][0]["evidence"][0]["quote"] = "this sentence was invented by a lazy worker"
    return v2, []


def m_pad(lens, v2):
    v2["claims"] = v2["claims"][:6]  # too few claims
    return v2, []


results = []
d = build("T0_honest")
j = run(d)
show("honest packet", j, "ACCEPT")
results.append(j["verdict"] == "ACCEPT")

for name, tf, rc in [("M1_short_quotes", m_short_quotes, "ok"), ("M2_shallow_read", m_shallow, "ok"), ("M3_silent_deletes", m_delete, "ok"),
                     ("M4_invented_quote", m_bad_quote, "ok"), ("M5_too_few_claims", m_pad, "ok"),
                     ("M6_no_receipts", None, "none"), ("M7_false_receipts", None, "false")]:
    d = build(name, tf, rc)
    j = run(d)
    show(name, j, "REJECT-ish")
    results.append(j["verdict"] != "ACCEPT")

# M8: forged verified file (claims tampered after verification, verified left untouched)
d = build("M8_forged_verified")
c2 = json.loads((d / "structure" / "claims_v2.json").read_text(encoding="utf-8"))
c2["claims"][0]["evidence"][0]["quote"] = "completely fabricated quotation that appears nowhere"
dump(d / "structure" / "claims_v2.json", c2)
j = run(d)
show("M8_forged_verified", j, "REJECT-ish")
results.append(j["verdict"] != "ACCEPT")

# M9: v1 edited after an acceptance run
d = build("M9_v1_edited")
run(d)  # first run stores the v1 fingerprint
c1 = json.loads((d / "structure" / "claims_v1.json").read_text(encoding="utf-8"))
c1["claims"][0]["claim"] += " (edited afterwards)"
dump(d / "structure" / "claims_v1.json", c1)
j = run(d)
show("M9_v1_edited_after_check", j, "REJECT-ish")
results.append(j["verdict"] != "ACCEPT")

# M10: tripwire (baseline entry altered to simulate a modified protected file)
base = WORK / "packets" / "tripwire.json"
saved = base.read_text(encoding="utf-8")
b = json.loads(saved)
b["protocol/battery.md"] = "0" * 64
base.write_text(json.dumps(b), encoding="utf-8")
d = build("M10_tripwire")
j = run(d)
base.write_text(saved, encoding="utf-8")  # restore
show("M10_tripwire", j, "REJECT-ish")
results.append(j["verdict"] == "REJECT")

print(f"\n{sum(results)}/{len(results)} checks behaved as expected")
sys.exit(0 if all(results) else 1)
