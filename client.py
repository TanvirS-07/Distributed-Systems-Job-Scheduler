#!/usr/bin/env python3
import os
import socket
import time
import xml.etree.ElementTree as ET
from collections import Counter

# basic client setup stuff
HOST = "localhost"
PORT = 50000
AUTH_NAME = "chicken"

# retry settings for loading the xml specs
SPEC_LOAD_RETRIES = 20
SPEC_LOAD_DELAY = 0.1

# fallback values in case xml doesnt load properly
DEFAULT_SERVER_LIMIT = 1
DEFAULT_BOOT_TIME = 60
DEFAULT_HOURLY_RATE = 1.0
DEFAULT_RESOURCE = 1

class DSClient:
    def __init__(self):

        # open socket connection to ds-server
        self.sock = socket.socket()
        self.sock.connect((HOST, PORT))
        self.reader = self.sock.makefile("r", encoding="utf-8", newline="\n")

    def send(self, message):

        # send message with newline cause server expects that
        self.sock.sendall((message + "\n").encode("utf-8"))

    def receive(self):

        # read one response line from server
        msg = self.reader.readline()
        if not msg:
            raise RuntimeError("Server closed connection")
        return msg.strip()

    def close(self):

         # close everything nicely at the end
        self.reader.close()
        self.sock.close()


def load_specs():

    # try loading server specs from ds-system.xml
    for _ in range(SPEC_LOAD_RETRIES):
        if os.path.exists("ds-system.xml"):
            root = ET.parse("ds-system.xml").getroot()
            specs = {}

            # store useful server info by server type
            for server in root.findall(".//server"):
                specs[server.attrib["type"]] = {
                    "limit": int(server.attrib.get("limit", DEFAULT_SERVER_LIMIT)),
                    "boot": int(server.attrib.get("bootupTime", DEFAULT_BOOT_TIME)),
                    "rate": float(server.attrib.get("hourlyRate", DEFAULT_HOURLY_RATE)),
                    "cores": int(server.attrib.get("cores", DEFAULT_RESOURCE)),
                    "memory": int(server.attrib.get("memory", DEFAULT_RESOURCE)),
                    "disk": int(server.attrib.get("disk", DEFAULT_RESOURCE)),
                }
            return specs
        time.sleep(SPEC_LOAD_DELAY)

        # if xml never loads just return empty specs
    return {}


def parse_server(line):
    p = line.split()
    return {
        "type": p[0],
        "id": int(p[1]),
        "state": p[2],
        "avail_cores": int(p[4]),
        "avail_memory": int(p[5]),
        "avail_disk": int(p[6]),
        "waiting": int(p[7]),
        "running": int(p[8]),
    }


def get_servers(client, query, cores, memory, disk):

    # ask server for either Avail or Capable servers
    client.send(f"GETS {query} {cores} {memory} {disk}")
    resp = client.receive()
    data = resp.split()

    # no matching servers
    if data[0] == "NONE" or int(data[1]) == 0:
        client.send("OK")
        client.receive()
        return []

    count = int(data[1])

    # first OK says ready to receive server list
    client.send("OK")
    servers = [parse_server(client.receive()) for _ in range(count)]

    # second OK tells server we got the list
    client.send("OK")
    client.receive()
    return servers


def choose_server(servers, specs):

    # helper to get spec values, or use fallback if missing
    def spec(s, key, fb):
        return specs.get(s["type"], {}).get(key, fb)

    def full_cores(s):
        return spec(s, "cores", s["avail_cores"])

    # pick server with:
    # 1. least waiting jobs
    # 2. biggest total server size
    # 3. biggest currently free resources
    # 4. lowest id as tie breaker
    return min(
        servers,
        key=lambda s: (
            s["waiting"],
            -full_cores(s),
            -s["avail_cores"],
            -s["avail_memory"],
            -s["avail_disk"],
            s["id"],
        ),
    )


class Stats:
    """Optional run summary, only printed when --stats or DS_STATS is set."""

    def __init__(self):
        self.jobs = 0
        self.avail_hits = 0
        self.capable_fallbacks = 0
        self.by_type = Counter()

    def record(self, server, fallback):
        self.jobs += 1
        if fallback:
            self.capable_fallbacks += 1
        else:
            self.avail_hits += 1
        self.by_type[server["type"]] += 1

    def report(self):
        lines = [
            "# client stats",
            f"# jobs scheduled:     {self.jobs}",
            f"# GETS Avail hits:    {self.avail_hits}",
            f"# GETS Capable used:  {self.capable_fallbacks}",
            "# jobs per server type:",
        ]
        for name, count in sorted(self.by_type.items()):
            lines.append(f"#   {name}: {count}")
        return "\n".join(lines)


def main():
    client = DSClient()
    
    # standard handshake
    client.send("HELO")
    client.receive()

    client.send(f"AUTH {AUTH_NAME}")
    client.receive()

    # load xml server specs once at the start
    specs = load_specs()

    while True:

        # ask for next job
        client.send("REDY")
        msg = client.receive()

        # no more jobs left
        if msg == "NONE":
            break

        parts = msg.split()

        # only schedule actual job messages
        if parts[0] in ("JOBN", "JOBP"):
            job = {
                "id": int(parts[1]),
                "submit": int(parts[2]),
                "cores": int(parts[3]),
                "memory": int(parts[4]),
                "disk": int(parts[5]),
                "runtime": int(parts[6]),
            }

            # first try servers that can run it right now
            servers = get_servers(client, "Avail", job["cores"], job["memory"], job["disk"])

            if not servers:

                # if none are free, just grab any capable server
                servers = get_servers(client, "Capable", job["cores"], job["memory"], job["disk"])
                server = servers[0]
            else:

                # if there are available servers, choose the better one
                server = choose_server(servers, specs)

            # send chosen server back to scheduler
            client.send(f"SCHD {job['id']} {server['type']} {server['id']}")
            client.receive()

    # clean exit
    client.send("QUIT")
    client.receive()
    client.close()


if __name__ == "__main__":
    main()