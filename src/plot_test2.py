#!/usr/bin/env python3
"""Test 2 chart: probe recall vs k, joint main probe, one panel per family, one row per model.

  .venv/bin/python src/plot_test2.py results/test2_panns_cnn14_<ts>.json results/test2_beats_<ts>.json

Writes results/figures/test2_recall_vs_k.png and .pdf, plus test2_recall_vs_k.csv (the table view
with every plotted number). Target and control instruments are solid lines, Western cousins dashed,
chance dotted. Bands are +/- 1 sd over the 10 draws. Numbers come only from the result files given.
"""
import csv, json, sys
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

sys.path.insert(0, str(Path(__file__).resolve().parent))
from eval_common import C  # noqa: E402

MODEL_NAME = {"panns_cnn14": "PANNs CNN14", "beats": "BEATs"}
FAMILY_ORDER = [("bowed", "Bowed"), ("plucked", "Plucked lute"), ("zither", "Zither"), ("wind", "Wind"), ("drum", "Drum")]
SERIES = ["#2a78d6", "#eb6834"]   # categorical slots 1-2 (reference palette, light), for targets/controls
COUSIN = "#52514e"                # text-secondary ink, dashed: Western cousin
INK, MUTED, GRID = "#0b0b0b", "#52514e", "#e4e3df"


def panels(main, ins):
    """family -> (targets in tradition order, cousin) restricted to the main class set."""
    out = {}
    for fam, _ in FAMILY_ORDER:
        tg = [c for c in main if ins[c]["family"] == fam and ins[c]["role"] != "cousin"]
        cz = sorted({ins[c]["cousin"] for c in tg if ins[c]["cousin"] in main})
        if tg:
            out[fam] = (tg, cz)
    return out


def main(paths):
    ins = C.instruments()
    runs = [json.load(open(p)) for p in paths]
    root = C.root() / "results" / "figures"
    root.mkdir(parents=True, exist_ok=True)
    plt.rcParams.update({"font.size": 9, "axes.edgecolor": MUTED, "axes.labelcolor": INK,
                         "xtick.color": MUTED, "ytick.color": MUTED, "font.family": "DejaVu Sans"})
    fig, axes = plt.subplots(len(runs), len(FAMILY_ORDER), figsize=(11, 2.6 * len(runs) + 0.6),
                             sharex=True, sharey=True, squeeze=False)
    rows = []
    for r, run in enumerate(runs):
        m = run["metrics"]
        main_set = m["main_class_set"]["classes"]
        joint = m["results"]["joint"]
        ks = [int(k) for k in joint]
        chance = joint[str(ks[0])]["chance"]
        pan = panels(main_set, ins)
        for col, (fam, title) in enumerate(FAMILY_ORDER):
            ax = axes[r][col]
            ax.set_facecolor("#fcfcfb")
            ax.grid(axis="y", color=GRID, linewidth=0.8)
            ax.set_axisbelow(True)
            for s in ("top", "right"):
                ax.spines[s].set_visible(False)
            ax.axhline(chance, color=MUTED, linestyle=":", linewidth=1.2)
            if r == 0:
                ax.set_title(title, color=INK, fontsize=10)
            if fam not in pan:
                continue
            tg, cz = pan[fam]
            series = [(c, SERIES[i], "-") for i, c in enumerate(tg)] + [(c, COUSIN, "--") for c in cz]
            ends = []
            for c, color, ls in series:
                mean = [joint[str(k)]["per_class"][c]["recall_mean"] for k in ks]
                sd = [joint[str(k)]["per_class"][c]["recall_sd"] for k in ks]
                ax.fill_between(ks, [a - b for a, b in zip(mean, sd)], [a + b for a, b in zip(mean, sd)],
                                color=color, alpha=0.10, linewidth=0)
                ax.plot(ks, mean, color=color, linestyle=ls, linewidth=2, marker="o", markersize=4.5,
                        markeredgecolor="#fcfcfb", markeredgewidth=1)
                ends.append([mean[-1], c.replace("_", " ") + (" †" if c in ("flute", "dizi") else "")])
                for k, a, b in zip(ks, mean, sd):
                    rows.append({"model": run["model"], "family": fam, "instrument": c,
                                 "role": ins[c]["role"], "tradition": ins[c]["group"], "k": k,
                                 "recall_mean": round(a, 4), "recall_sd": round(b, 4),
                                 "n_test": joint[str(k)]["per_class"][c]["n_test"], "chance": round(chance, 4)})
            # end labels pushed apart so they never overlap (min gap in data units); the lines stay exact
            ends.sort()
            for j in range(1, len(ends)):
                ends[j][0] = max(ends[j][0], ends[j - 1][0] + 0.075)
            for y, label in ends:
                ax.annotate(label, (ks[-1], y), xytext=(6, 0), textcoords="offset points",
                            va="center", fontsize=8, color=INK)
        axes[r][0].set_ylabel(f"{MODEL_NAME.get(run['model'], run['model'])}\nrecall (test split)")
    for ax in axes[-1]:
        ax.set_xticks(ks)
        ax.set_xlabel("k (training clips per class)")
        ax.set_xlim(0, ks[-1] + 6)
    axes[0][0].set_ylim(0, 1.05)
    from matplotlib.lines import Line2D
    key = [Line2D([], [], color=INK, lw=2, label="target or control instrument (solid, colored)"),
           Line2D([], [], color=COUSIN, lw=2, ls="--", label="Western cousin (dashed, gray)"),
           Line2D([], [], color=MUTED, lw=1.2, ls=":", label=f"chance ({chance:.2f}, 11 classes)")]
    fig.legend(handles=key, loc="upper center", ncol=3, frameon=False, fontsize=9, bbox_to_anchor=(0.5, 1.0))
    fig.text(0.01, 0.005, "Joint probe over 11 classes; mean of 10 draws, band = ±1 sd. "
             "† flute and dizi mix recordings uploaded as flute and as dizi; 20 of 24 flute test clips were uploaded as dizi (docs/results_notes.md).",
             fontsize=7.5, color=MUTED)
    fig.tight_layout(rect=(0, 0.03, 1, 0.94))
    for ext in ("png", "pdf"):
        fig.savefig(root / f"test2_recall_vs_k.{ext}", dpi=200, facecolor="#fcfcfb")
    with open(root / "test2_recall_vs_k.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0]))
        w.writeheader()
        w.writerows(rows)
    meta = {"sources": [str(p) for p in paths]}
    (root / "test2_recall_vs_k.sources.txt").write_text("\n".join(meta["sources"]) + "\n", encoding="utf-8")
    print("wrote", root / "test2_recall_vs_k.png")


if __name__ == "__main__":
    main(sys.argv[1:])
