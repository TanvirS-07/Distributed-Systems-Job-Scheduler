import io
import os
import socket
import sys
import threading

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, os.path.dirname(__file__))

from test_client import FakeClient, run_mock_server, server_line, srv  # noqa: E402

import client  # noqa: E402

# --- trace_path ---------------------------------------------------------------


def test_trace_path_flag_with_space():
    assert client.trace_path(["client.py", "--trace", "out.txt"], {}) == "out.txt"


def test_trace_path_flag_with_equals():
    assert client.trace_path(["client.py", "--trace=out.txt"], {}) == "out.txt"


def test_trace_path_env_var():
    assert client.trace_path(["client.py"], {"DS_TRACE": "env.txt"}) == "env.txt"


def test_trace_path_off_by_default():
    assert client.trace_path(["client.py"], {}) is None
    assert client.trace_path(["client.py", "--stats"], {}) is None


def test_trace_path_flag_wins_over_env():
    assert client.trace_path(["client.py", "--trace=a.txt"], {"DS_TRACE": "b.txt"}) == "a.txt"


def test_trace_path_dangling_flag_ignored():
    assert client.trace_path(["client.py", "--trace"], {}) is None


# --- Tracer -------------------------------------------------------------------


def test_tracer_line_lists_candidates_and_choice():
    buf = io.StringIO()
    tracer = client.Tracer(buf)
    job = {"id": 7, "cores": 2, "memory": 400, "disk": 900}
    small, large = srv("small", 0, waiting=1), srv("large", 3, cores=8)
    tracer.record(job, "Avail", [small, large], large)

    line = buf.getvalue()
    assert line.startswith("job 7 cores=2 mem=400 disk=900 via=Avail")
    assert "small 0 (w=1" in line and "large 3" in line
    assert line.rstrip().endswith("-> large 3")


def test_tracer_open_writes_file(tmp_path):
    path = tmp_path / "trace.txt"
    tracer = client.Tracer.open(str(path))
    tracer.record({"id": 1, "cores": 1, "memory": 1, "disk": 1}, "Capable", [srv()], srv())
    tracer.close()
    assert path.read_text().startswith("job 1 ")


# --- end to end: --trace ------------------------------------------------------


def test_main_writes_trace_file(tmp_path, monkeypatch):
    listener = socket.socket()
    listener.bind(("127.0.0.1", 0))
    listener.listen(1)

    jobs = ["JOBN 0 10 1 100 100 50", "JOBN 1 20 1 100 100 50"]
    avail = [server_line("small", 0), server_line("large", 1, cores=8)]
    log = []
    t = threading.Thread(target=run_mock_server, args=(listener, jobs, avail, [], log), daemon=True)
    t.start()

    trace_file = tmp_path / "decisions.txt"
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(client, "PORT", listener.getsockname()[1])
    monkeypatch.setattr(client, "HOST", "127.0.0.1")
    monkeypatch.setattr(client, "SPEC_LOAD_RETRIES", 1)
    monkeypatch.setattr(client, "SPEC_LOAD_DELAY", 0)
    monkeypatch.setattr(sys, "argv", ["client.py", f"--trace={trace_file}"])

    client.main()
    t.join(timeout=5)
    listener.close()

    lines = trace_file.read_text().splitlines()
    assert len(lines) == 2
    assert all("via=Avail" in ln for ln in lines)


def test_main_without_flags_creates_no_files(tmp_path, monkeypatch, capsys):
    listener = socket.socket()
    listener.bind(("127.0.0.1", 0))
    listener.listen(1)
    t = threading.Thread(
        target=run_mock_server,
        args=(listener, ["JOBN 0 10 1 100 100 50"], [server_line("small", 0)], [], []),
        daemon=True,
    )
    t.start()

    monkeypatch.chdir(tmp_path)
    monkeypatch.delenv("DS_STATS", raising=False)
    monkeypatch.delenv("DS_TRACE", raising=False)
    monkeypatch.setattr(client, "PORT", listener.getsockname()[1])
    monkeypatch.setattr(client, "HOST", "127.0.0.1")
    monkeypatch.setattr(client, "SPEC_LOAD_RETRIES", 1)
    monkeypatch.setattr(client, "SPEC_LOAD_DELAY", 0)
    monkeypatch.setattr(sys, "argv", ["client.py"])

    client.main()
    t.join(timeout=5)
    listener.close()

    assert list(tmp_path.iterdir()) == []
    assert capsys.readouterr().err == ""


# --- get_servers edge cases ---------------------------------------------------


def test_get_servers_none_keyword():
    fake = FakeClient(["NONE", "."])
    assert client.get_servers(fake, "Avail", 1, 1, 1) == []
    assert fake.sent[-1] == "OK"
