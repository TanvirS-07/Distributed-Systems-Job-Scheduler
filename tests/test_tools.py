import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import export_results  # noqa: E402
import log_summary  # noqa: E402
import make_gantt  # noqa: E402
import workload_report  # noqa: E402

ALGOS = ["atl", "ff", "bf", "fc", "fafc"]


def ref_row(**kw):
    base = {"atl": 1000, "ff": 200, "bf": 210, "fc": 900, "fafc": 190}
    base.update(kw)
    return base


def make_results(client_tt):
    """Client and reference dicts shaped like results/*.json for the given {config: client_value} map."""
    ref = {"Turnaround time": {c: ref_row() for c in client_tt}}
    client = {"Turnaround time": dict(client_tt)}
    return client, ref


# --- workload_report ----------------------------------------------------------


def test_parse_config_name():
    assert workload_report.parse_config_name("config040-long-high.xml") == ("long", "high")
    assert workload_report.parse_config_name("config012-med-alt.xml") == ("med", "alt")
    assert workload_report.parse_config_name("ds-sample-config01.xml") is None


def test_build_report_groups_and_wins():
    client, ref = make_results({
        "config010-short-low.xml": 150,   # beats best baseline 190
        "config020-short-high.xml": 250,  # loses
        "config030-long-high.xml": 100,   # beats
    })
    report = workload_report.build_report(client, ref)

    by_length = {r["group"]: r for r in report["length"]}
    assert by_length["short"]["configs"] == 2 and by_length["short"]["wins"] == 1
    assert by_length["long"]["wins"] == 1
    assert by_length["short"]["yours"] == pytest.approx(200)
    # diff: (150-190)/190 and (250-190)/190 averaged
    assert by_length["short"]["diff_pct"] == pytest.approx(((150 - 190) / 190 + (250 - 190) / 190) / 2 * 100)

    by_load = {r["group"]: r for r in report["load"]}
    assert by_load["high"]["configs"] == 2 and by_load["low"]["configs"] == 1


def test_build_report_orders_groups():
    client, ref = make_results({
        "config010-long-low.xml": 100,
        "config010-short-low.xml": 100,
        "config010-med-low.xml": 100,
    })
    order = [r["group"] for r in workload_report.build_report(client, ref)["length"]]
    assert order == ["short", "med", "long"]


def test_build_report_skips_missing_results_and_unknown_names():
    client, ref = make_results({"config010-short-low.xml": 100, "other.xml": 100})
    client["Turnaround time"]["config020-short-low.xml"] = None
    ref["Turnaround time"]["config020-short-low.xml"] = ref_row()
    report = workload_report.build_report(client, ref)
    assert report["length"][0]["configs"] == 1


def test_build_report_utilisation_higher_is_better():
    ref = {"Resource utilisation": {"config010-short-low.xml": {a: 50.0 for a in ALGOS}}}
    client = {"Resource utilisation": {"config010-short-low.xml": 60.0}}
    report = workload_report.build_report(client, ref, "Resource utilisation")
    assert report["length"][0]["wins"] == 1


def test_format_report_has_both_sections():
    client, ref = make_results({"config010-short-low.xml": 150})
    text = workload_report.format_report(workload_report.build_report(client, ref), "Turnaround time")
    assert "By job length" in text and "By job load" in text and "short" in text


# --- export_results -----------------------------------------------------------


def test_metric_table_bolds_best_and_adds_average():
    client, ref = make_results({"config010-short-low.xml": 150, "config020-short-low.xml": 300})
    lines = export_results.metric_table(client, ref, "Turnaround time")
    text = "\n".join(lines)
    assert "| Config | ATL | FF | BF | FC | FAFC | Yours |" in text
    assert "**150**" in text            # client best on first config
    assert "**190**" in text            # FAFC best on second config
    assert "**Average**" in text


def test_metric_table_empty_when_no_data():
    assert export_results.metric_table({"Turnaround time": {}}, {"Turnaround time": {}}, "Turnaround time") == []


def test_build_markdown_skips_metrics_without_data():
    client, ref = make_results({"config010-short-low.xml": 150})
    md = export_results.build_markdown(client | {"Resource utilisation": {}, "Total rental cost": {}},
                                       ref | {"Resource utilisation": {}, "Total rental cost": {}})
    assert "### Turnaround time" in md
    assert "### Resource utilisation" not in md


# --- log_summary --------------------------------------------------------------

LOG = """\
t 10: job 0 -- CPU: 1, Mem: 1, Disk: 1, Est Runtime: 100 SUBMITTED
t 30: job 0 on tiny 0 RUNNING
t 130: job 0 on tiny 0 COMPLETED
t 20: job 1 -- CPU: 1, Mem: 1, Disk: 1, Est Runtime: 50 SUBMITTED
t 20: job 1 on tiny 1 RUNNING
t 70: job 1 on tiny 1 COMPLETED
t 40: job 2 -- CPU: 1, Mem: 1, Disk: 1, Est Runtime: 50 SUBMITTED
""".splitlines()


def test_summarise_times():
    s = log_summary.summarise(make_gantt.parse_log(LOG))
    assert s["jobs"] == 2 and s["incomplete"] == 1
    assert s["avg_wait"] == pytest.approx(10)       # (20 + 0) / 2
    assert s["avg_exec"] == pytest.approx(75)       # (100 + 50) / 2
    assert s["avg_turnaround"] == pytest.approx(85)
    assert s["end_time"] == 130
    assert s["servers"][("tiny", 0)] == {"jobs": 1, "busy": 100}


def test_summarise_empty_log():
    assert log_summary.summarise({}) == {}


def test_format_summary_lists_servers():
    text = log_summary.format_summary(log_summary.summarise(make_gantt.parse_log(LOG)))
    assert "tiny 0" in text and "avg turnaround time: 85.0" in text


# --- make_gantt edge cases ----------------------------------------------------


def test_gantt_skips_incomplete_jobs():
    chart = make_gantt.build_gantt(make_gantt.parse_log(LOG))
    assert "Job 2" not in chart and "Job 0:" in chart


def test_gantt_no_waiting_bar_when_started_immediately():
    chart = make_gantt.build_gantt(make_gantt.parse_log(LOG))
    assert "Job 1 Waiting" not in chart and "Job 0 Waiting: crit, 10, 30" in chart


# --- plot_results smoke tests -------------------------------------------------


def test_plots_are_written(tmp_path):
    pytest.importorskip("matplotlib")
    import plot_results

    ref = {m: {"config010-short-low.xml": {a: float(i + 1) * 10 for i, a in enumerate(ALGOS)}}
           for m in plot_results.METRICS}
    client = {m: {"config010-short-low.xml": 25.0} for m in plot_results.METRICS}

    plot_results.per_config_chart(client, ref, str(tmp_path / "a.png"))
    plot_results.vs_best_chart(client, ref, str(tmp_path / "b.png"))
    plot_results.averages_chart(client, ref, str(tmp_path / "c.png"))
    assert all((tmp_path / n).stat().st_size > 0 for n in ("a.png", "b.png", "c.png"))
