#!/usr/bin/env python3
"""Plot client results against the ds-client baselines.

Usage:
    python3 plot_results.py                       # reads results/*.json, writes diagrams/*.png
    python3 plot_results.py -t results/test_results.json -o diagrams

Requires matplotlib (pip install matplotlib).
"""
import json
import os
from argparse import ArgumentParser
from statistics import mean

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

BASELINE = ["atl", "ff", "bf", "fc", "fafc"]
COLOURS = {"atl": "#b0b0b0", "ff": "#8fb8de", "bf": "#5f8fc4", "fc": "#d9b38c", "fafc": "#3b6ea5", "yours": "#d1495b"}
METRICS = ["Turnaround time", "Resource utilisation", "Total rental cost"]
HIGHER_IS_BETTER = {"Resource utilisation"}


def load(path):
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def usable_configs(client, ref, metric="Turnaround time"):
    """Configs that have both a client result and reference results."""
    return [
        c for c, v in client[metric].items()
        if isinstance(v, (int, float)) and c in ref[metric]
    ]


def per_config_chart(client, ref, out_path, metric="Turnaround time"):
    configs = usable_configs(client, ref, metric)
    series = BASELINE + ["yours"]
    width = 0.8 / len(series)
    fig, ax = plt.subplots(figsize=(max(8, len(configs) * 0.9), 5))

    for i, name in enumerate(series):
        vals = [client[metric][c] if name == "yours" else ref[metric][c][name] for c in configs]
        xs = [x + i * width for x in range(len(configs))]
        ax.bar(xs, vals, width, label=name.upper() if name != "yours" else "Yours", color=COLOURS[name])

    ax.set_xticks([x + 0.4 - width / 2 for x in range(len(configs))])
    ax.set_xticklabels([c.replace(".xml", "") for c in configs], rotation=60, ha="right", fontsize=8)
    ax.set_ylabel(metric + (" (log scale)" if metric == "Turnaround time" else ""))
    if metric == "Turnaround time":
        ax.set_yscale("log")
    ax.set_title(f"{metric} per config")
    ax.legend(ncol=len(series), fontsize=8)
    fig.tight_layout()
    fig.savefig(out_path, dpi=150)
    plt.close(fig)


def vs_best_chart(client, ref, out_path, metric="Turnaround time"):
    """Percent difference to the best baseline per config (negative = better for lower-is-better metrics)."""
    configs = usable_configs(client, ref, metric)
    pick = max if metric in HIGHER_IS_BETTER else min
    diffs = []
    for c in configs:
        best = pick(ref[metric][c][a] for a in BASELINE)
        diffs.append((client[metric][c] - best) / best * 100 if best else 0.0)

    better = (lambda d: d > 0) if metric in HIGHER_IS_BETTER else (lambda d: d < 0)
    fig, ax = plt.subplots(figsize=(8, max(4, len(configs) * 0.3)))
    colours = ["#4c9f70" if better(d) else "#d1495b" for d in diffs]
    ax.barh([c.replace(".xml", "") for c in configs], diffs, color=colours)
    ax.axvline(0, color="black", linewidth=0.8)
    ax.invert_yaxis()
    ax.set_xlabel("% difference vs best baseline")
    ax.set_title(f"{metric}: yours vs best baseline per config")
    fig.tight_layout()
    fig.savefig(out_path, dpi=150)
    plt.close(fig)


def averages_chart(client, ref, out_path):
    """Average of each metric, normalised to the mean of the baselines (lower is better except utilisation)."""
    fig, axes = plt.subplots(1, len(METRICS), figsize=(12, 4))
    series = BASELINE + ["yours"]
    for ax, metric in zip(axes, METRICS):
        configs = usable_configs(client, ref, metric)
        if not configs:
            ax.set_visible(False)
            continue
        avgs = {a: mean(ref[metric][c][a] for c in configs) for a in BASELINE}
        avgs["yours"] = mean(client[metric][c] for c in configs)
        ax.bar([s.upper() if s != "yours" else "Yours" for s in series], [avgs[s] for s in series],
               color=[COLOURS[s] for s in series])
        ax.set_title(metric + (" (higher better)" if metric in HIGHER_IS_BETTER else " (lower better)"), fontsize=9)
        if metric == "Turnaround time":
            ax.set_yscale("log")
        ax.tick_params(axis="x", labelsize=8)
    fig.tight_layout()
    fig.savefig(out_path, dpi=150)
    plt.close(fig)


def main():
    parser = ArgumentParser(description="Plot client results against the baseline algorithms")
    parser.add_argument("-t", "--client_results", default="results/test_results.json")
    parser.add_argument("-r", "--reference_results", default="results/ref_results.json")
    parser.add_argument("-o", "--output_dir", default="diagrams")
    args = parser.parse_args()

    client = load(args.client_results)
    ref = load(args.reference_results)
    os.makedirs(args.output_dir, exist_ok=True)

    outputs = {
        "turnaround_per_config.png": lambda p: per_config_chart(client, ref, p),
        "turnaround_vs_best.png": lambda p: vs_best_chart(client, ref, p),
        "averages.png": lambda p: averages_chart(client, ref, p),
    }
    for name, draw in outputs.items():
        path = os.path.join(args.output_dir, name)
        draw(path)
        print("Wrote", path)


if __name__ == "__main__":
    main()
