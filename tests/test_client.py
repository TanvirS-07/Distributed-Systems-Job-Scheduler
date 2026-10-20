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
