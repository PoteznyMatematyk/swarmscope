"""Figures and evidence generation for wikiswarm: visualization of swarm dynamics."""
from __future__ import annotations

import argparse
import json
import math
import sys
from datetime import datetime
from pathlib import Path

# Headless backend for matplotlib
import matplotlib
matplotlib.use("Agg")
import matplotlib.dates as mdates
import matplotlib.pyplot as plt
import numpy as np

# Ensure ROOT is on sys.path
ROOT = Path(__file__).resolve().parent.parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from gate.common import FIRST_HAND, digits, norm_item, read_jsonl, write_json  # noqa: E402

WORK = ROOT / "work"

# Colour-blind safe palette (Okabe & Ito)
COLOR_ORANGE = "#D55E00"
COLOR_BLUE = "#0072B2"
COLOR_GREEN = "#009E73"
COLOR_PURPLE = "#CC79A7"
COLOR_SKY = "#56B4E9"
COLOR_YELLOW = "#E69F00"
COLOR_DARK = "#333333"


def parse_iso(s: str) -> datetime:
    return datetime.fromisoformat(s.replace("Z", "+00:00"))


def generate_all(
    metrics_path: Path,
    tuples_path: Path,
    figures_dir: Path,
    evidence_dir: Path,
) -> dict:
    figures_dir.mkdir(parents=True, exist_ok=True)
    evidence_dir.mkdir(parents=True, exist_ok=True)

    with open(metrics_path, encoding="utf-8") as f:
        metrics = json.loads(f.read())

    tuples = list(read_jsonl(tuples_path))
    for t in tuples:
        t["nitem"] = norm_item(t.get("item"))
        t["nvalue"] = digits(t.get("value")) or None

    # Step 1: Assign null-round tuples according to single-matching unit
    unit_keys = {(u["family"], u["round"], u["item"]) for u in metrics["units"]}
    assigned_tuples = []
    for t in tuples:
        if t.get("round") is None:
            matching = [k for (fam, k, item) in unit_keys if fam == t["family"] and item == t["nitem"]]
            if len(matching) == 1:
                t_copy = dict(t)
                t_copy["round"] = matching[0]
                assigned_tuples.append(t_copy)
        else:
            assigned_tuples.append(t)

    # Group tuples by unit
    unit_tuples_map = {k: [] for k in unit_keys}
    for t in assigned_tuples:
        key = (t["family"], t["round"], t["nitem"])
        if key in unit_tuples_map:
            unit_tuples_map[key].append(t)

    # -------------------------------------------------------------
    # 4. work/evidence/units.jsonl
    # -------------------------------------------------------------
    evidence_units_path = evidence_dir / "units.jsonl"
    evidence_rows = []
    leads_list = []

    # Map unit key to unit dict from metrics
    metrics_units_map = {(u["family"], u["round"], u["item"]): u for u in metrics["units"]}

    for key in sorted(unit_keys):
        fam, rnd, item = key
        u_info = metrics_units_map[key]
        consensus = u_info.get("consensus_value")
        ts = unit_tuples_map[key]
        ts.sort(key=lambda t: (t["wall_time"], t["record_id"]))
        fh = [t for t in ts if t["kind"] in FIRST_HAND]

        # Reveal tuple
        reveal_tuple = None
        if consensus is not None:
            for t in ts:
                if (t["kind"] in FIRST_HAND or t["kind"] == "relayed") and t["nvalue"] == consensus:
                    reveal_tuple = {
                        "record_id": t["record_id"],
                        "wall_time": t["wall_time"],
                        "signature": t.get("signature"),
                        "quote": t["quote"],
                    }
                    break

        revealer = u_info.get("revealer")
        reveal_time = u_info.get("reveal_time")

        # Receivers: distinct non-null signatures in fh excluding revealer
        fh_sigs = {t["signature"] for t in fh if t.get("signature") is not None}
        if revealer is not None:
            rx_sigs = sorted(fh_sigs - {revealer})
        else:
            rx_sigs = sorted(fh_sigs)

        rx_evidence = []
        for sig in rx_sigs:
            sig_fh = [t for t in fh if t.get("signature") == sig]
            first_fh = sig_fh[0]
            rx_evidence.append({
                "record_id": first_fh["record_id"],
                "wall_time": first_fh["wall_time"],
                "signature": sig,
                "quote": first_fh["quote"],
            })
            if reveal_time is not None and first_fh["wall_time"] > reveal_time:
                lead = (parse_iso(first_fh["wall_time"]) - parse_iso(reveal_time)).total_seconds() / 60.0
                leads_list.append(lead)

        evidence_rows.append({
            "family": fam,
            "round": rnd,
            "item": item,
            "reveal": reveal_tuple,
            "receivers": rx_evidence,
        })

    with open(evidence_units_path, "w", encoding="utf-8") as f:
        for r in evidence_rows:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")

    # -------------------------------------------------------------
    # 1. work/figures/reveal_vs_receivers.svg
    # Top 6 families with most units
    # -------------------------------------------------------------
    top_fams = [
        fam for fam, _ in sorted(
            metrics.get("n_units_by_family", {}).items(),
            key=lambda x: -x[1],
        )[:6]
    ]

    selected_units = [
        u for u in metrics["units"]
        if u["family"] in top_fams
    ]
    # Sort by family, then round, then item
    selected_units.sort(key=lambda u: (top_fams.index(u["family"]), u["round"], u["item"]))

    n_rows = len(selected_units)
    fig_height = max(5.0, n_rows * 0.45 + 1.5)
    fig, ax = plt.subplots(figsize=(12, fig_height), facecolor="white")
    ax.set_facecolor("white")

    y_labels = []
    has_reveal_legend = False
    has_rx_legend = False

    for idx, u in enumerate(selected_units):
        y = n_rows - 1 - idx  # top to bottom
        key = (u["family"], u["round"], u["item"])
        y_labels.append(f"{u['family']} R{u['round']} ({u['item']})")

        # Plot reveal
        rev_t_str = u.get("reveal_time")
        if rev_t_str:
            rev_dt = parse_iso(rev_t_str)
            lbl = "Answer reveal" if not has_reveal_legend else None
            ax.plot(rev_dt, y, "o", color=COLOR_ORANGE, markersize=8, zorder=5, label=lbl)
            has_reveal_legend = True

        # Plot receivers
        ev_unit = next((e for e in evidence_rows if (e["family"], e["round"], e["item"]) == key), None)
        if ev_unit:
            for rx in ev_unit["receivers"]:
                rx_dt = parse_iso(rx["wall_time"])
                lbl = "Receiver first report" if not has_rx_legend else None
                ax.plot(rx_dt, y, "|", color=COLOR_GREEN, markersize=14, markeredgewidth=2.5, zorder=4, label=lbl)
                has_rx_legend = True

    ax.set_yticks(range(n_rows))
    ax.set_yticklabels(reversed(y_labels), fontsize=9)
    ax.xaxis.set_major_formatter(mdates.DateFormatter("%Y-%m-%d %H:%M"))
    fig.autofmt_xdate(rotation=20)
    ax.grid(axis="x", color="#E0E0E0", linestyle="--", alpha=0.7)
    ax.set_title("Timings of answer reveal vs receiver reports across rounds (UTC)", fontsize=13, pad=12)
    if has_reveal_legend or has_rx_legend:
        ax.legend(loc="upper right", frameon=True, facecolor="white", edgecolor="#CCCCCC")
    plt.tight_layout()
    fig1_path = figures_dir / "reveal_vs_receivers.svg"
    fig.savefig(fig1_path, format="svg", dpi=100)
    plt.close(fig)

    # -------------------------------------------------------------
    # 2. work/figures/lead_minutes.svg
    # Histogram of leads (minutes, log-x)
    # -------------------------------------------------------------
    fig, ax = plt.subplots(figsize=(12, 6), facecolor="white")
    ax.set_facecolor("white")

    pos_leads = [x for x in leads_list if x > 0]
    if pos_leads:
        min_lead = min(pos_leads)
        max_lead = max(pos_leads)
        if min_lead == max_lead:
            bins = np.array([min_lead * 0.5, min_lead * 1.5])
        else:
            log_min = math.floor(math.log10(max(min_lead, 0.1)))
            log_max = math.ceil(math.log10(max(max_lead, 1.0)))
            bins = np.logspace(log_min, log_max, num=25)
        ax.hist(pos_leads, bins=bins, color=COLOR_BLUE, edgecolor="white", alpha=0.85)
        ax.set_xscale("log")
    else:
        ax.text(0.5, 0.5, "No exposed receivers with positive lead time", ha="center", va="center")

    median_val = metrics.get("lead_minutes_median")
    if pos_leads and median_val is not None:
        ax.axvline(median_val, color=COLOR_ORANGE, linestyle="--", linewidth=2,
                   label=f"Median lead: {median_val:.1f} min")
        ax.legend(loc="upper right", frameon=True, facecolor="white", edgecolor="#CCCCCC")

    med_label = f"{median_val:.1f} min" if median_val is not None else "N/A"
    ax.set_xlabel("Lead time before receiver report (minutes, log scale)", fontsize=11)
    ax.set_ylabel("Number of exposed receivers", fontsize=11)
    ax.set_title(
        f"Distribution of lead times (Median: {med_label} | "
        f"Exposed receivers: {metrics.get('exposed_upper', 0)} / {metrics.get('receiver_rounds', 0)} | "
        f"Confirmed cache use: {metrics.get('confirmed_use', 0)})",
        fontsize=12, pad=12
    )
    ax.grid(color="#E0E0E0", linestyle="--", alpha=0.7)
    plt.tight_layout()
    fig2_path = figures_dir / "lead_minutes.svg"
    fig.savefig(fig2_path, format="svg", dpi=100)
    plt.close(fig)

    # -------------------------------------------------------------
    # 3. work/figures/wrong_predictions.svg
    # Bar per wrong prediction: n_signatures, labelled family R<k> <item>
    # -------------------------------------------------------------
    wrong_preds = metrics.get("wrong_predictions", [])
    fig_height = max(4.5, len(wrong_preds) * 0.45 + 1.5)
    fig, ax = plt.subplots(figsize=(12, fig_height), facecolor="white")
    ax.set_facecolor("white")

    if wrong_preds:
        labels = [f"{p['family']} R{p['round']} {p['item']}" for p in wrong_preds]
        counts = [p["n_signatures"] for p in wrong_preds]
        y_pos = np.arange(len(labels))
        ax.barh(y_pos, counts, color=COLOR_PURPLE, edgecolor="none", height=0.6)
        ax.set_yticks(y_pos)
        ax.set_yticklabels(labels, fontsize=10)
        ax.invert_yaxis()  # top down
        ax.set_xlabel("Number of distinct agent signatures repeating prediction", fontsize=11)
        ax.set_title("Propagation of unconfirmed predictions across agent runs", fontsize=12, pad=12)
        ax.grid(axis="x", color="#E0E0E0", linestyle="--", alpha=0.7)
    else:
        ax.text(0.5, 0.5, "No wrong predictions observed", ha="center", va="center")
        ax.set_title("Unconfirmed predictions across agent runs", fontsize=12, pad=12)

    plt.tight_layout()
    fig3_path = figures_dir / "wrong_predictions.svg"
    fig.savefig(fig3_path, format="svg", dpi=100)
    plt.close(fig)

    # -------------------------------------------------------------
    # 5. work/figures/manifest.json
    # Every number printed on a figure, with its source key in metrics.json
    # -------------------------------------------------------------
    manifest = {
        "lead_minutes_median": metrics.get("lead_minutes_median"),
        "exposed_upper": metrics.get("exposed_upper", 0),
        "receiver_rounds": metrics.get("receiver_rounds", 0),
        "confirmed_use": metrics.get("confirmed_use", 0),
    }
    manifest_path = figures_dir / "manifest.json"
    write_json(manifest_path, manifest)

    return manifest


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate figures and evidence for wikiswarm")
    parser.add_argument("--metrics", type=Path, default=WORK / "metrics.json", help="Path to metrics.json")
    parser.add_argument("--tuples", type=Path, default=WORK / "tuples_verified.jsonl", help="Path to tuples_verified.jsonl")
    parser.add_argument("--figures-dir", type=Path, default=WORK / "figures", help="Directory for figures")
    parser.add_argument("--evidence-dir", type=Path, default=WORK / "evidence", help="Directory for evidence")
    args = parser.parse_args()

    manifest = generate_all(args.metrics, args.tuples, args.figures_dir, args.evidence_dir)
    print(f"Generated figures and evidence. Manifest: {manifest}")


if __name__ == "__main__":
    main()
