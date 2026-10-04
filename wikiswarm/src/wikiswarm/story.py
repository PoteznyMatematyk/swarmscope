"""The two results we lead with, computed only from gate-verified tuples:

1. Foreknowledge (per family): agents who named a round's question in an earlier post, before reporting
   that they received it, after another agent had already put it on the wiki.
2. The OECD precision flip: one evidence post on 20 June 04:56:50 UTC and the swarm's switch from padded
   two-decimal values (16.40 / 9.90 / 14.60 / 23.10 / 9.70) to dashboard values (16.38 / 9.91 / 14.59 / 23.13 / 9.69).

    python -m wikiswarm.story      (after wikiswarm.aggregate and wikiswarm.foreknowledge)
Writes work/story.json and work/figures/{foreknowledge,oecd_flip}.{svg,png}.
"""
from __future__ import annotations

import json
import sys
from collections import Counter, defaultdict
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
import re  # noqa: E402

from gate.common import SIG_RE, digits, norm_item, norm_time, read_jsonl, write_json, ws  # noqa: E402

WORK = ROOT / "work"
FIG = WORK / "figures"
FLIP_TIME = "2026-06-20T04:56:50Z"
FLIP_RECORD = "811ecec4836dffba37faf126fb71f28db81f07aeb529673619a791b792843d04"
PADDED = {"poland": "1640", "hungary": "990", "slovak republic": "1460", "slovenia": "2310", "czech republic": "970"}
DASHBOARD = {"poland": "1638", "hungary": "991", "slovak republic": "1459", "slovenia": "2313", "czech republic": "969"}
OLD_C, NEW_C, GREY = "#E69F00", "#0072B2", "#999999"   # Okabe-Ito


def oecd_flip(tuples: list[dict]) -> dict:
    rows = []
    for t in tuples:
        if t["family"] != "oecd-equity" or not t.get("wall_time") or not t.get("value"):
            continue
        i, v = norm_item(t["item"]), digits(t["value"])
        side = "padded" if PADDED.get(i) == v else "dashboard" if DASHBOARD.get(i) == v else None
        if side:
            rows.append({**t, "side": side, "nitem": i})
    rows.sort(key=lambda r: (r["wall_time"], r["record_id"]))
    flip_rows = [r for r in rows if r["record_id"] == FLIP_RECORD]
    ans = defaultdict(Counter)
    for r in rows:
        if r["kind"] == "answered":
            ans["before" if r["wall_time"] < FLIP_TIME else "after_06" if r["wall_time"] >= "2026-06-20T06:00:00Z" else "between"][r["side"]] += 1
    first = defaultdict(dict)
    for r in rows:
        if r["signature"]:
            first[r["signature"]].setdefault(r["side"], r["wall_time"])
    switched = sorted(s for s, d in first.items() if "padded" in d and "dashboard" in d and d["padded"] < d["dashboard"])
    switched_back = sorted(s for s, d in first.items() if "padded" in d and "dashboard" in d and d["dashboard"] < d["padded"])
    hourly = defaultdict(Counter)
    for r in rows:
        if r["wall_time"] >= "2026-06-19T22:00:00Z":
            hourly[r["wall_time"][:13]][r["side"]] += 1
    return {
        "flip_time": FLIP_TIME, "flip_record": FLIP_RECORD,
        "flip_signature": flip_rows[0]["signature"] if flip_rows else None,
        "flip_quote": flip_rows[0]["quote"] if flip_rows else None,
        "answered": {k: dict(v) for k, v in ans.items()},
        "signatures_padded": sum(1 for d in first.values() if "padded" in d),
        "signatures_dashboard": sum(1 for d in first.values() if "dashboard" in d),
        "switched_padded_to_dashboard": len(switched), "switched_dashboard_to_padded": len(switched_back),
        "hourly": {h: dict(c) for h, c in sorted(hourly.items())},
    }


CITES = re.compile(r"tooltip|Mar30|aria|Power ?BI|PBI|querydata|DSR|rendered|dashboard|DOM", re.I)
REPRODUCES = re.compile(r"replicat|reproduc|independent(ly)?\b|I (also )?(obtained|captured|rendered|intercepted|verified|bypassed)"
                        r"|we (also )?(obtained|captured|rendered|intercepted|verified|bypassed)", re.I)


def own_segment(text: str, quote: str) -> str:
    """The part of a record written by the author of `quote`: from the previous '-- Name' to the next one."""
    t, q = ws(text), ws(quote)
    pos = t.find(q)
    prev = [m.end() for m in SIG_RE.finditer(t, 0, max(pos, 0))]
    nxt = SIG_RE.search(t, pos + len(q)) if pos >= 0 else None
    return t[(prev[-1] if prev else 0):(nxt.end() if nxt else len(t))]


def oecd_switchers(tuples: list[dict]) -> dict:
    texts = {}
    for p in read_jsonl(WORK / "posts.jsonl"):
        texts.setdefault(p["record_id"], p["text"])
    first = defaultdict(dict)
    rows = []
    for t in tuples:
        if t["family"] != "oecd-equity" or not t.get("value") or not t["signature"] or not norm_time(t.get("wall_time")):
            continue
        i, v = norm_item(t["item"]), digits(t["value"])
        side = "padded" if PADDED.get(i) == v else "dashboard" if DASHBOARD.get(i) == v else None
        if side:
            rows.append((norm_time(t["wall_time"]), t["record_id"], t["signature"], side, t["quote"]))
    for w, rid, sig, side, q in sorted(rows):
        first[sig].setdefault(side, (w, rid, q))
    out = []
    for sig, d in first.items():
        if "padded" in d and "dashboard" in d and d["padded"][0] < d["dashboard"][0]:
            w, rid, q = d["dashboard"]
            seg = own_segment(texts[rid], q)
            out.append({"signature": sig, "first_padded": d["padded"][0], "switch_time": w, "record_id": rid,
                        "cites_evidence": bool(CITES.search(seg)), "says_reproduced": bool(REPRODUCES.search(seg)),
                        "segment": seg[:400]})
    out.sort(key=lambda x: x["switch_time"])
    lines = ["# OECD task: the 24 agents that switched from padded to dashboard values", "",
             "Generated by `python -m wikiswarm.story`. For each agent: the time of its first post with a dashboard",
             "value, keyword flags computed on its own segment of that post (cites the dashboard evidence; says it",
             "reproduced it), and the start of the segment. Keyword flags are a screen, not a verdict: read the text.", ""]
    for x in out:
        flags = ", ".join(f for f, on in (("cites evidence", x["cites_evidence"]), ("says reproduced", x["says_reproduced"])) if on) or "no flag"
        lines += [f"**`{x['signature']}`**, switch {x['switch_time'][5:16].replace('T', ' ')} UTC ({flags})", "",
                  "> " + x["segment"].replace("|", "\\|"), ""]
    (WORK / "OECD_SWITCHERS.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    return {"n": len(out), "cites_evidence": sum(x["cites_evidence"] for x in out),
            "says_reproduced_keyword": sum(x["says_reproduced"] for x in out)}


def fig_flip(d: dict) -> None:
    from datetime import datetime, timedelta
    start, end = datetime(2026, 6, 19, 23), datetime(2026, 6, 20, 14)
    hours = [(start + timedelta(hours=i)).strftime("%Y-%m-%dT%H") for i in range(int((end - start).seconds / 3600) + 1)]
    x = list(range(len(hours)))
    pad = [d["hourly"].get(h, {}).get("padded", 0) for h in hours]
    das = [d["hourly"].get(h, {}).get("dashboard", 0) for h in hours]
    fig, ax = plt.subplots(figsize=(11, 4.6), dpi=110)
    ax.bar(x, pad, color=OLD_C, label="padded: 16.40, 9.90, 14.60, 23.10, 9.70")
    ax.bar(x, das, bottom=pad, color=NEW_C, label="dashboard: 16.38, 9.91, 14.59, 23.13, 9.69")
    fx = hours.index(FLIP_TIME[:13]) - 0.5 + 56 / 60
    ax.axvline(fx, color="black", lw=1.2, ls="--")
    ax.annotate("04:56 UTC: one agent posts the dashboard's\nraw values and how it obtained them",
                xy=(fx, 60), xytext=(fx + 4.4, 92), fontsize=9,
                arrowprops=dict(arrowstyle="->", color="black", lw=0.8))
    ax.set_xticks(x)
    ax.set_xticklabels([h[11:13] for h in hours], fontsize=8)
    ax.set_xlim(-0.6, len(hours) - 0.4)
    ax.set_xlabel("hour (UTC), 19 June 23:00 to 20 June 14:00")
    ax.set_ylabel("verified mentions per hour")
    ax.set_title("OECD equity task: the value agents posted for the same five rounds", fontsize=11, loc="left")
    ax.set_ylim(0, 128)
    ax.legend(frameon=False, fontsize=9, loc="upper left", ncol=2)
    ax.spines[["top", "right"]].set_visible(False)
    fig.tight_layout()
    for ext in ("svg", "png"):
        fig.savefig(FIG / f"oecd_flip.{ext}")
    plt.close(fig)


def foreknowledge_by_family(fk: dict) -> list[dict]:
    fam = defaultdict(Counter)
    for u in fk["units"]:
        for k in ("receivers", "item_ahead", "value_ahead", "item_ahead_after_other"):
            fam[u["family"]][k] += u[k]
    rows = [{"family": f, **c} for f, c in fam.items() if c["item_ahead"] > 0]
    return sorted(rows, key=lambda r: -r["item_ahead"])


def fig_foreknowledge(rows: list[dict]) -> None:
    rows = rows[:12][::-1]
    y = list(range(len(rows)))
    fig, ax = plt.subplots(figsize=(10, 5.2), dpi=110)
    ax.barh(y, [r["item_ahead"] for r in rows], color=NEW_C, label="named the question in an earlier post")
    ax.barh(y, [r["value_ahead"] for r in rows], color="#56B4E9", height=0.45, label="... and the answer value too")
    for yi, r in zip(y, rows):
        ax.text(r["item_ahead"] + 0.6, yi, f"of {r['receivers']} reports", va="center", fontsize=8, color="#444444")
    ax.set_yticks(y)
    ax.set_yticklabels([r["family"].replace("datausa-", "DataUSA ").replace("-", " ") for r in rows], fontsize=9)
    ax.set_xlabel("agent-rounds")
    ax.set_title("Agents who knew a round's question before their own run received it", fontsize=11, loc="left")
    ax.legend(frameon=False, fontsize=9, loc="lower right")
    ax.spines[["top", "right"]].set_visible(False)
    fig.tight_layout()
    for ext in ("svg", "png"):
        fig.savefig(FIG / f"foreknowledge.{ext}")
    plt.close(fig)


def main() -> None:
    tuples = list(read_jsonl(WORK / "tuples_verified.jsonl"))
    fk = json.loads((WORK / "foreknowledge.json").read_text(encoding="utf-8"))
    FIG.mkdir(parents=True, exist_ok=True)
    flip = oecd_flip(tuples)
    flip["switchers"] = oecd_switchers(tuples)
    fam = foreknowledge_by_family(fk)
    fig_flip(flip)
    fig_foreknowledge(fam)
    write_json(WORK / "story.json", {"foreknowledge_totals": fk["totals"], "foreknowledge_by_family": fam, "oecd_flip": flip})
    print(json.dumps({"foreknowledge": fk["totals"], "oecd_answered": flip["answered"],
                      "switched": flip["switched_padded_to_dashboard"], "switched_back": flip["switched_dashboard_to_padded"],
                      "switchers": flip["switchers"]}))


if __name__ == "__main__":
    main()
