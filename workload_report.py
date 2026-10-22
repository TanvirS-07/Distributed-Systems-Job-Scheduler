#!/usr/bin/env python3
"""Break client results down by workload type.

Config names look like config040-long-high.xml: <servers>-<job length>-<load>.
This groups results by job length and by load and compares the client with the best baseline.

Usage:
    python3 workload_report.py
    python3 workload_report.py -t results/test_results.json -m "Total rental cost"
"""
import json
import re
from argparse import ArgumentParser
from collections import defaultdict
from statistics import mean
from typing import Dict, List, Optional, Tuple

BASELINE = ["atl", "ff", "bf", "fc", "fafc"]
HIGHER_IS_BETTER = {"Resource utilisation"}
LENGTH_ORDER = ["short", "med", "long"]
LOAD_ORDER = ["low", "med", "high"]

re_config = re.compile(r"^config\d+-(?P<length>[a-z]+)-(?P<load>[a-z]+)\.xml$")


def parse_config_name(name: str) -> Optional[Tuple[str, str]]:
    """Return (length, load) for a TestConfigs style file name, or None for other names."""
    m = re_config.match(name)
    if not m:
        return None
    return m.group("length"), m.group("load")


def best_baseline(ref_row: Dict[str, float], metric: str) -> float:
    pick = max if metric in HIGHER_IS_BETTER else min
    return pick(ref_row[a] for a in BASELINE)


def build_report(client: dict, ref: dict, metric: str = "Turnaround time") -> Dict[str, List[dict]]:
    """Group per-config results by length and by load.

    Each row has: group, configs, yours (mean), best (mean best baseline), diff_pct (mean % vs best) and wins
    (configs where the client strictly beats every baseline).
    """
    buckets: Dict[str, Dict[str, list]] = {"length": defaultdict(list), "load": defaultdict(list)}
    for config, value in client[metric].items():
        parsed = parse_config_name(config)
        if parsed is None or not isinstance(value, (int, float)) or config not in ref[metric]:
            continue
        best = best_baseline(ref[metric][config], metric)
        better = value > best if metric in HIGHER_IS_BETTER else value < best
        row = (value, best, (value - best) / best * 100 if best else 0.0, better)
        buckets["length"][parsed[0]].append(row)
        buckets["load"][parsed[1]].append(row)

    report: Dict[str, List[dict]] = {}
    for kind, order in (("length", LENGTH_ORDER), ("load", LOAD_ORDER)):
        groups = buckets[kind]
        names = [n for n in order if n in groups] + sorted(n for n in groups if n not in order)
        report[kind] = [
            {
                "group": name,
                "configs": len(groups[name]),
                "yours": mean(r[0] for r in groups[name]),
                "best": mean(r[1] for r in groups[name]),
                "diff_pct": mean(r[2] for r in groups[name]),
                "wins": sum(1 for r in groups[name] if r[3]),
            }
            for name in names
        ]
    return report


def format_report(report: Dict[str, List[dict]], metric: str) -> str:
    out = [f"{metric} by workload (diff is vs best baseline, mean per config)"]
    for kind in ("length", "load"):
        out.append("")
        out.append(f"By job {kind}")
        out.append(f"{'group':<8}{'configs':>8}{'yours':>12}{'best base':>12}{'diff %':>9}{'wins':>6}")
        for r in report[kind]:
            out.append(
                f"{r['group']:<8}{r['configs']:>8}{r['yours']:>12.2f}{r['best']:>12.2f}"
                f"{r['diff_pct']:>+9.2f}{r['wins']:>4}/{r['configs']}"
            )
    return "\n".join(out)


def main() -> None:
    parser = ArgumentParser(description="Break results down by workload type")
    parser.add_argument("-t", "--client_results", default="results/test_results.json")
    parser.add_argument("-r", "--reference_results", default="results/ref_results.json")
    parser.add_argument("-m", "--metric", default="Turnaround time",
                        choices=["Turnaround time", "Resource utilisation", "Total rental cost"])
    args = parser.parse_args()

    with open(args.client_results, encoding="utf-8") as f:
        client = json.load(f)
    with open(args.reference_results, encoding="utf-8") as f:
        ref = json.load(f)

    print(format_report(build_report(client, ref, args.metric), args.metric))


if __name__ == "__main__":
    main()
