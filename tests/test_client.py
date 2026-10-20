import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import client  # noqa: E402


class FakeClient:
    """Stands in for DSClient: records sends and replays scripted replies."""

    def __init__(self, replies):
        self.replies = list(replies)
        self.sent = []

    def send(self, message):
        self.sent.append(message)

    def receive(self):
        return self.replies.pop(0)


def server_line(stype, sid, state="active", cores=4, mem=8000, disk=64000, waiting=0, running=0):
    return f"{stype} {sid} {state} 0 {cores} {mem} {disk} {waiting} {running}"


def srv(stype="small", sid=0, waiting=0, cores=2, mem=1000, disk=1000):
    return {"type": stype, "id": sid, "state": "active", "avail_cores": cores,
            "avail_memory": mem, "avail_disk": disk, "waiting": waiting, "running": 0}


# --- parse_server -----------------------------------------------------------

def test_parse_server_fields():
    s = client.parse_server(server_line("medium", 3, "booting", 4, 8000, 64000, 2, 1))
    assert s == {"type": "medium", "id": 3, "state": "booting", "avail_cores": 4,
                 "avail_memory": 8000, "avail_disk": 64000, "waiting": 2, "running": 1}


# --- get_servers ------------------------------------------------------------

def test_get_servers_returns_parsed_list():
    fake = FakeClient(["DATA 2 124", server_line("tiny", 0), server_line("tiny", 1), "."])
    servers = client.get_servers(fake, "Avail", 1, 100, 100)
    assert [s["id"] for s in servers] == [0, 1]
    assert fake.sent == ["GETS Avail 1 100 100", "OK", "OK"]


def test_get_servers_none_response():
    fake = FakeClient(["DATA 0 0", "."])
    assert client.get_servers(fake, "Capable", 99, 1, 1) == []
    assert fake.sent == ["GETS Capable 99 1 1", "OK"]


# --- choose_server (tie-break order) ----------------------------------------

SPECS = {"small": {"cores": 2}, "large": {"cores": 8}}


def test_fewest_waiting_jobs_wins_first():
    a, b = srv("large", 0, waiting=3), srv("small", 1, waiting=0)
    assert client.choose_server([a, b], SPECS) is b


def test_bigger_total_cores_breaks_waiting_tie():
    a, b = srv("small", 0), srv("large", 1)
    assert client.choose_server([a, b], SPECS) is b


def test_more_available_cores_next():
    a, b = srv("small", 0, cores=1), srv("small", 1, cores=2)
    assert client.choose_server([a, b], SPECS) is b


def test_more_available_memory_then_disk():
    a, b = srv("small", 0, mem=500), srv("small", 1, mem=900)
    assert client.choose_server([a, b], SPECS) is b
    c, d = srv("small", 0, disk=500), srv("small", 1, disk=900)
    assert client.choose_server([c, d], SPECS) is d


def test_lowest_id_is_final_tiebreak():
    a, b = srv("small", 5), srv("small", 2)
    assert client.choose_server([a, b], SPECS) is b


def test_unknown_type_falls_back_to_available_cores():
    a, b = srv("mystery", 0, cores=1), srv("mystery", 1, cores=3)
    assert client.choose_server([a, b], {}) is b


# --- load_specs -------------------------------------------------------------

def test_load_specs_reads_xml(tmp_path, monkeypatch):
    (tmp_path / "ds-system.xml").write_text(
        '<system><servers>'
        '<server type="tiny" limit="4" bootupTime="40" hourlyRate="0.2" cores="2" memory="2000" disk="4000"/>'
        '</servers></system>'
    )
    monkeypatch.chdir(tmp_path)
    specs = client.load_specs()
    assert specs["tiny"] == {"limit": 4, "boot": 40, "rate": 0.2, "cores": 2, "memory": 2000, "disk": 4000}


def test_load_specs_missing_file_returns_empty(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(client, "SPEC_LOAD_RETRIES", 2)
    monkeypatch.setattr(client, "SPEC_LOAD_DELAY", 0)
    assert client.load_specs() == {}


# --- Stats ------------------------------------------------------------------

def test_stats_counts_and_report():
    stats = client.Stats()
    stats.record(srv("small"), fallback=False)
    stats.record(srv("small"), fallback=False)
    stats.record(srv("large"), fallback=True)
    assert (stats.jobs, stats.avail_hits, stats.capable_fallbacks) == (3, 2, 1)
    report = stats.report()
    assert "small: 2" in report and "large: 1" in report
