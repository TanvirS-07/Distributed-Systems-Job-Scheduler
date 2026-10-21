#!/usr/bin/env python3
"""Turn a ds-server log into a Mermaid Gantt chart.

Usage:
    ./ds-server -n -c configs/stage2/s2-config02.xml -v all > run.log
    python3 make_gantt.py run.log -o diagrams/run.mmd

Waiting time (submit -> running) is drawn as a red bar, execution as a normal one.
"""
import re
import sys
from argparse import ArgumentParser

# events sharing a timestamp with the line above omit the "t N:" prefix, so it is optional here
re_time = re.compile(r"^t (\d+):")
re_submitted = re.compile(r"^\s*(?:t \d+: )?job (\d+) --.*SUBMITTED")
re_running = re.compile(r"^\s*(?:t \d+: )?job (\d+) on (\S+) (\d+) RUNNING")
re_completed = re.compile(r"^\s*(?:t \d+: )?job (\d+) on (\S+) (\d+) COMPLETED")


def parse_log(lines):
    """Return {job_id: {"submit", "server", "start", "end"}} from ds-server log lines."""
    jobs = {}
    now = 0
    for line in lines:
        m = re_time.match(line.lstrip())
        if m:
            now = int(m.group(1))

        m = re_submitted.match(line)
        if m:
            jobs.setdefault(int(m.group(1)), {})["submit"] = now
            continue

        m = re_running.match(line)
        if m:
            job = jobs.setdefault(int(m.group(1)), {})
            job["start"] = now
            job["server"] = (m.group(2), int(m.group(3)))
            continue

        m = re_completed.match(line)
        if m:
            jobs.setdefault(int(m.group(1)), {})["end"] = now
    return jobs


def build_gantt(jobs, title="ds-sim Job Scheduling Gantt Chart"):
    sections = {}
    for job_id, job in sorted(jobs.items()):
        if not all(k in job for k in ("submit", "start", "end", "server")):
            continue
        rows = sections.setdefault(job["server"], [])
        if job["start"] > job["submit"]:
            rows.append(f"Job {job_id} Waiting: crit, {job['submit']}, {job['start']}")
        rows.append(f"Job {job_id}: {job['start']}, {job['end']}")

    out = [
        "gantt",
        f"    title {title}",
        "    dateFormat X",
        "    axisFormat %s",
    ]
    for (stype, sid), rows in sorted(sections.items()):
        out.append("")
        out.append(f"    section {stype} {sid}")
        out.extend(f"    {row}" for row in rows)
    return "\n".join(out) + "\n"


def main():
    parser = ArgumentParser(description="Convert a ds-server log (-v all) into a Mermaid Gantt chart")
    parser.add_argument("log", help="ds-server log file")
    parser.add_argument("-o", "--output", help="output .mmd file (default: stdout)")
    parser.add_argument("-t", "--title", default="ds-sim Job Scheduling Gantt Chart")
    args = parser.parse_args()

    with open(args.log, encoding="utf-8") as f:
        jobs = parse_log(f)

    if not jobs:
        print("Error: no job events found in log", file=sys.stderr)
        sys.exit(1)

    chart = build_gantt(jobs, args.title)
    if args.output:
        with open(args.output, "w", encoding="utf-8") as f:
            f.write(chart)
        print(f"Wrote {args.output} ({len(jobs)} jobs)")
    else:
        print(chart, end="")


if __name__ == "__main__":
    main()
