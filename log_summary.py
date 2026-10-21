#!/usr/bin/env python3
"""Summarise a ds-server log (-v all) without relying on the simulator's own summary lines.

Usage:
    ./ds-server -n -c configs/stage2/s2-config02.xml -v all > run.log
    python3 log_summary.py run.log
"""
import sys
from argparse import ArgumentParser
from collections import defaultdict
from statistics import mean
from typing import Dict

from make_gantt import parse_log


def summarise(jobs: Dict[int, dict]) -> dict:
    """Compute waiting/execution/turnaround time and per-server load from parsed jobs (see make_gantt.parse_log)."""
    done = {i: j for i, j in jobs.items() if all(k in j for k in ("submit", "start", "end", "server"))}
    if not done:
        return {}

    waits = [j["start"] - j["submit"] for j in done.values()]
    execs = [j["end"] - j["start"] for j in done.values()]
    turnarounds = [j["end"] - j["submit"] for j in done.values()]

    per_server: Dict[tuple, dict] = defaultdict(lambda: {"jobs": 0, "busy": 0})
    for j in done.values():
        per_server[j["server"]]["jobs"] += 1
        per_server[j["server"]]["busy"] += j["end"] - j["start"]

    return {
        "jobs": len(done),
        "incomplete": len(jobs) - len(done),
        "avg_wait": mean(waits),
        "max_wait": max(waits),
        "avg_exec": mean(execs),
        "avg_turnaround": mean(turnarounds),
        "end_time": max(j["end"] for j in done.values()),
        "servers": dict(per_server),
    }


def format_summary(s: dict) -> str:
    lines = [
        f"jobs completed:      {s['jobs']} ({s['incomplete']} incomplete)",
        f"simulation end time: {s['end_time']}",
        f"avg waiting time:    {s['avg_wait']:.1f} (max {s['max_wait']})",
        f"avg execution time:  {s['avg_exec']:.1f}",
        f"avg turnaround time: {s['avg_turnaround']:.1f}",
        "",
        f"{'server':<16}{'jobs':>6}{'busy time':>12}",
    ]
    for (stype, sid), info in sorted(s["servers"].items()):
        lines.append(f"{stype + ' ' + str(sid):<16}{info['jobs']:>6}{info['busy']:>12}")
    return "\n".join(lines)


def main() -> None:
    parser = ArgumentParser(description="Summarise a ds-server log")
    parser.add_argument("log", help="ds-server log file")
    args = parser.parse_args()

    with open(args.log, encoding="utf-8") as f:
        summary = summarise(parse_log(f))

    if not summary:
        print("Error: no completed jobs found in log", file=sys.stderr)
        sys.exit(1)
    print(format_summary(summary))


if __name__ == "__main__":
    main()
