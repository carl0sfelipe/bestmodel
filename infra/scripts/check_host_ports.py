"""Pre-flight guard: refuse to publish host ports reserved by the colocated stack.

Runs `docker compose config`, extracts every published host port and fails hard
when any of them collides with a reserved production port. Wired into
`make infra-up` so the local stack can only start on its remapped ports.
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

COMPOSE_FILE = Path(__file__).resolve().parent.parent / "docker" / "docker-compose.yml"

RESERVED_HOST_PORTS = {5432, 6379, 9000, 9001, 7700, 3010, 8888}


def published_host_ports() -> dict[str, list[int]]:
    raw = subprocess.run(
        ["docker", "compose", "-f", str(COMPOSE_FILE), "config", "--format", "json"],
        capture_output=True,
        text=True,
        check=True,
    ).stdout
    config = json.loads(raw)
    ports_by_service: dict[str, list[int]] = {}
    for service_name, service in config.get("services", {}).items():
        published = []
        for port_mapping in service.get("ports", []):
            if isinstance(port_mapping, dict) and port_mapping.get("published") is not None:
                published.append(int(str(port_mapping["published"]).split("-")[0]))
            elif isinstance(port_mapping, str):
                published.append(int(port_mapping.split(":")[0]))
        ports_by_service[service_name] = published
    return ports_by_service


def main() -> int:
    ports_by_service = published_host_ports()
    violations = [
        f"{service_name} publishes reserved host port {port}"
        for service_name, ports in ports_by_service.items()
        for port in ports
        if port in RESERVED_HOST_PORTS
    ]
    if violations:
        print("port guard FAILED:", file=sys.stderr)
        for violation in violations:
            print(f"  - {violation}", file=sys.stderr)
        return 1
    for service_name, ports in sorted(ports_by_service.items()):
        print(f"ok: {service_name} -> host ports {ports or '(none)'}")
    print("port guard passed: no reserved host port is published")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
