"""Async logic to start DHCP services and collect client leases via telnet."""

from __future__ import annotations

import asyncio
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any, MutableMapping, Sequence

from .config_store import ConfigStore
from .nodes import resolve_console_target
from .telnet_client import run_command, run_command_sequence

SWITCH_KEYWORDS = ("switch", "openvswitch", "ovs")
SERVER_KEYWORDS = ("dhcp", "dnsmasq")

DHCP_START_COMMAND = "/usr/local/bin/start.sh"
DHCLIENT_COMMAND = "dhclient -v -1"
IP_SHOW_COMMAND = "ip -4 addr show"

IPV4_RE = re.compile(r"\binet\s+(\d+\.\d+\.\d+\.\d+)/(\d+)")


def is_switch(name: str) -> bool:
    lowered = (name or "").lower()
    return any(keyword in lowered for keyword in SWITCH_KEYWORDS)


def is_dhcp_server(name: str) -> bool:
    name = (name or "").lower()
    return any(keyword in name for keyword in SERVER_KEYWORDS)


def extract_first_ipv4(output: str | None) -> str | None:
    if not output:
        return None
    match = IPV4_RE.search(output)
    if match:
        return match.group(1)
    return None


@dataclass(slots=True)
class NodeExecutionResult:
    name: str
    host: str
    port: int
    action: str
    success: bool
    output: str | None = None
    error: str | None = None
    assigned_ip: str | None = None


@dataclass(slots=True)
class DHCPAssignResult:
    server_results: list[NodeExecutionResult]
    client_results: list[NodeExecutionResult]
    changed: bool
    backup_path: Path | None


class DHCPAssigner:
    def __init__(self, store: ConfigStore) -> None:
        self._store = store

    async def assign(
        self,
        *,
        gns3_server_ip: str | None = None,
        dhclient_timeout: float = 15.0,
        dhcp_warmup: float = 0.0,
    ) -> DHCPAssignResult:
        data = self._store.load()
        nodes_value = data.get("nodes")
        if not isinstance(nodes_value, list):
            raise ValueError("config missing 'nodes' list")

        nodes = [n for n in nodes_value if isinstance(n, MutableMapping)]

        server_results = await self._start_servers(nodes, gns3_server_ip)

        if dhcp_warmup > 0:
            await asyncio.sleep(dhcp_warmup)

        client_results, changed = await self._run_clients(nodes, gns3_server_ip, dhclient_timeout)

        backup_path = None
        if changed:
            backup_path = self._store.backup()
            self._store.write(data)

        return DHCPAssignResult(
            server_results=server_results,
            client_results=client_results,
            changed=changed,
            backup_path=backup_path,
        )

    async def _start_servers(
        self,
        nodes: Sequence[MutableMapping[str, Any]],
        gns3_server_ip: str | None,
    ) -> list[NodeExecutionResult]:
        results: list[NodeExecutionResult] = []
        for node in nodes:
            name = str(node.get("name", ""))
            if not is_dhcp_server(name):
                continue

            target = resolve_console_target(node, gns3_server_ip)
            if target is None:
                results.append(
                    NodeExecutionResult(
                        name=name,
                        host="",
                        port=0,
                        action="start-server",
                        success=False,
                        error="Missing console settings",
                    )
                )
                continue

            host, port = target
            try:
                output = await run_command(host, port, DHCP_START_COMMAND, read_duration=5.0)
                results.append(
                    NodeExecutionResult(
                        name=name,
                        host=host,
                        port=port,
                        action="start-server",
                        success=True,
                        output=output,
                    )
                )
            except Exception as exc:
                results.append(
                    NodeExecutionResult(
                        name=name,
                        host=host,
                        port=port,
                        action="start-server",
                        success=False,
                        error=str(exc),
                    )
                )

        return results

    async def _run_clients(
        self,
        nodes: Sequence[MutableMapping[str, Any]],
        gns3_server_ip: str | None,
        dhclient_timeout: float,
    ) -> tuple[list[NodeExecutionResult], bool]:
        results: list[NodeExecutionResult] = []
        changed = False

        for node in nodes:
            name = str(node.get("name", ""))
            if is_dhcp_server(name) or is_switch(name):
                results.append(
                    NodeExecutionResult(
                        name=name,
                        host="",
                        port=0,
                        action="dhclient",
                        success=True,
                        output="skipped",
                    )
                )
                continue

            target = resolve_console_target(node, gns3_server_ip)
            if target is None:
                previous_ip = node.get("assigned_ip")
                if previous_ip is not None:
                    node["assigned_ip"] = None
                    changed = True
                results.append(
                    NodeExecutionResult(
                        name=name,
                        host="",
                        port=0,
                        action="dhclient",
                        success=False,
                        error="Missing console settings",
                    )
                )
                continue

            host, port = target
            try:
                output = await run_command_sequence(
                    host,
                    port,
                    [
                        (DHCLIENT_COMMAND, dhclient_timeout),
                        (IP_SHOW_COMMAND, 1.0),
                    ],
                    inter_command_delay=1.0,
                )
                ip = extract_first_ipv4(output)
                previous_ip = node.get("assigned_ip")
                if previous_ip != ip:
                    node["assigned_ip"] = ip
                    changed = True
                results.append(
                    NodeExecutionResult(
                        name=name,
                        host=host,
                        port=port,
                        action="dhclient",
                        success=True,
                        output=output,
                        assigned_ip=ip,
                    )
                )
            except Exception as exc:
                previous_ip = node.get("assigned_ip")
                if previous_ip is not None:
                    node["assigned_ip"] = None
                    changed = True
                results.append(
                    NodeExecutionResult(
                        name=name,
                        host=host,
                        port=port,
                        action="dhclient",
                        success=False,
                        error=str(exc),
                    )
                )

        return results, changed
