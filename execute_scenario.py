#!/usr/bin/env python3
"""Open a GNS3 project, start all nodes, then run server and client scripts."""

from __future__ import annotations

import asyncio
import concurrent.futures
import ipaddress
import shlex
import time
from dataclasses import dataclass
from typing import Iterable, List, Sequence

import requests

from core.gns3_client import GNS3Client
from core.nodes import resolve_console_target
from core.telnet_client import TelnetSettings, open_console
from core.template_cache import TemplateCacheError, load_registry
from models import APISettings


# ========= Edit these lines =========
PROJECT_NAME = "ae3gis-root-2"

# GNS3 server IPs / ranges to target (inclusive ranges). All servers share credentials.
TARGET_GNS3_SERVERS = [
	"10.193.80.120-10.193.80.130",
]

# Remote script locations inside the containers.
REMOTE_SERVER_SCRIPT = "/usr/local/bin/run_server.sh"
REMOTE_DHCP_SCRIPT = "/usr/local/bin/run_dhcp.sh"
REMOTE_CLIENT_SCRIPT = "/usr/local/bin/run_http2.sh"

# Concurrency and timing knobs.
SCRIPT_RUN_TIMEOUT = 120.0
SCRIPT_RUN_CONCURRENCY = 16
PROJECT_OPEN_TIMEOUT = 120.0
PROJECT_OPEN_POLL_INTERVAL = 2.0
NODE_START_TIMEOUT = 180.0
NODE_POLL_INTERVAL = 2.0
SCRIPT_SHELL = "/bin/sh"
SERVER_CONCURRENCY = 5
# ========= ================== =========


@dataclass(slots=True)
class TargetProject:
	project_id: str
	name: str


@dataclass(slots=True)
class NodeRun:
	name: str
	node_id: str
	host: str
	port: int
	command: str


def expand_targets(targets: Iterable[str]) -> List[str]:
	"""Expand individual IPs and inclusive ranges into a sorted list of addresses."""

	ips: set[str] = set()
	for entry in targets:
		if not entry:
			continue
		text = entry.strip()
		if not text:
			continue
		if "-" in text:
			left, right = (part.strip() for part in text.split("-", 1))
			start = ipaddress.IPv4Address(left)
			end = ipaddress.IPv4Address(right)
			if start > end:
				start, end = end, start
			for value in range(int(start), int(end) + 1):
				ips.add(str(ipaddress.IPv4Address(value)))
		else:
			ips.add(str(ipaddress.IPv4Address(text)))
	return sorted(ips, key=lambda addr: int(ipaddress.IPv4Address(addr)))


def load_project_info(project_name: str) -> TargetProject:
	settings = APISettings()  # type: ignore[call-arg]
	try:
		registry = load_registry(settings.templates_cache_path)
	except TemplateCacheError as exc:  # pragma: no cover - startup guard
		raise SystemExit(
			f"{exc}\nStart the FastAPI service once so it can populate the template cache."
		) from exc

	project_source = registry.get("projects") or {}
	project_lookup = {
		str(name): str(identifier)
		for name, identifier in getattr(project_source, "items", lambda: [])()
		if isinstance(name, str) and isinstance(identifier, str)
	}

	if project_name not in project_lookup:
		available = ", ".join(sorted(project_lookup)) or "<none>"
		raise SystemExit(
			"Project not found in cache: "
			+ project_name
			+ f". Available projects: {available}."
			+ "\nStart the FastAPI service to refresh the cache or update PROJECT_NAME."
		)

	return TargetProject(project_id=project_lookup[project_name], name=project_name)


def make_gns3_client(base_url: str, username: str | None, password: str | None) -> GNS3Client:
	session = requests.Session()
	if username and password:
		session.auth = (username, password)
	session.headers.update({"Accept": "application/json"})
	return GNS3Client(base_url=base_url.rstrip("/"), session=session)


def open_project(client: GNS3Client, project_id: str) -> None:
	client.post(f"/v2/projects/{project_id}/open")
	deadline = time.monotonic() + PROJECT_OPEN_TIMEOUT
	while True:
		info = client.get(f"/v2/projects/{project_id}")
		status = str(info.get("status", "")).lower()
		if status == "opened":
			return
		if time.monotonic() >= deadline:
			raise RuntimeError(f"Project {project_id} did not open within timeout")
		time.sleep(PROJECT_OPEN_POLL_INTERVAL)


def list_nodes(client: GNS3Client, project_id: str) -> List[dict]:
	data = client.get(f"/v2/projects/{project_id}/nodes")
	if isinstance(data, list):
		return [dict(node) for node in data if isinstance(node, dict)]
	raise RuntimeError(f"Unexpected node payload: {data!r}")


def ensure_nodes_started(client: GNS3Client, project_id: str, nodes: Sequence[dict]) -> List[dict]:
	pending = [n for n in nodes if str(n.get("status", "")).lower() != "started" and n.get("node_id")]
	if pending:
		bulk_started = False
		try:
			if len(pending) > 1:
				client.post(f"/v2/projects/{project_id}/nodes/start")
				bulk_started = True
		except requests.HTTPError as exc:  # type: ignore[attr-defined]
			status_code = getattr(exc.response, "status_code", None)
			if status_code not in {404, 405, 501}:
				raise
			print("  Bulk start not supported; falling back to per-node start.")

		if not bulk_started:
			for node in pending:
				node_id = node.get("node_id")
				name = node.get("name") or node_id
				print(f"  Starting node {name} ({node_id})")
				client.post(f"/v2/projects/{project_id}/nodes/{node_id}/start")

	deadline = time.monotonic() + NODE_START_TIMEOUT
	while True:
		refreshed = list_nodes(client, project_id)
		remaining = [n for n in refreshed if str(n.get("status", "")).lower() != "started"]
		if not remaining:
			return refreshed
		if time.monotonic() >= deadline:
			names = ", ".join(str(n.get("name") or n.get("node_id")) for n in remaining)
			raise RuntimeError(f"Nodes failed to reach started state: {names}")
		time.sleep(NODE_POLL_INTERVAL)


def categorize_nodes(nodes: Iterable[dict]) -> tuple[List[str], List[str], List[str]]:
	dhcp_nodes: List[str] = []
	server_nodes: List[str] = []
	client_nodes: List[str] = []

	for node in nodes:
		name = str(node.get("name") or "").strip()
		if not name:
			continue
		if name.lower().startswith("dhcp-"):
			dhcp_nodes.append(name)
		elif name.lower().startswith("server-"):
			server_nodes.append(name)
		elif name.lower().startswith("client-"):
			client_nodes.append(name)
	return dhcp_nodes, server_nodes, client_nodes


async def _run_single_script(run: NodeRun) -> None:
	command = run.command
	if SCRIPT_SHELL:
		command = f"{SCRIPT_SHELL} -c {shlex.quote(run.command)}"
	settings = TelnetSettings(host=run.host, port=run.port)
	async with open_console(settings) as console:
		output, exit_code = await console.run_command_with_status(
			command,
			read_duration=SCRIPT_RUN_TIMEOUT,
		)
		if exit_code not in (None, 0):
			raise RuntimeError(
				f"Script command failed on {run.name} (exit {exit_code}). Output:\n{output.strip()}"
			)


def run_scripts(runs: List[NodeRun], label: str) -> None:
	if not runs:
		print(f"  No {label} scripts to run.")
		return

	print(f"  Running {label} scripts on {len(runs)} node(s)...")

	async def _runner() -> None:
		limit = max(1, min(SCRIPT_RUN_CONCURRENCY, len(runs)))
		semaphore = asyncio.Semaphore(limit)

		async def _guarded(run: NodeRun) -> None:
			async with semaphore:
				await _run_single_script(run)

		await asyncio.gather(*(_guarded(run) for run in runs))

	asyncio.run(_runner())

	print(f"  Completed {label} scripts.")


def process_server(
	gns3_ip: str,
	project: TargetProject,
	settings: APISettings,
) -> None:
	base_url = f"http://{gns3_ip}:{settings.gns3_server_port}".rstrip("/")
	username = settings.gns3_username or "gns3"
	password = settings.gns3_password or "gns3"

	print(f"Processing GNS3 server {gns3_ip} (project {project.name})")

	client = make_gns3_client(base_url, username, password)
	try:
		open_project(client, project.project_id)
		nodes = list_nodes(client, project.project_id)
		print(f"  Found {len(nodes)} node(s) in project.")
		nodes = ensure_nodes_started(client, project.project_id, nodes)

		node_lookup = {
			str(node.get("name") or "").strip(): node
			for node in nodes
			if isinstance(node.get("node_id"), str) and str(node.get("name") or "").strip()
		}

		def _to_run(name: str, command: str) -> NodeRun:
			node = node_lookup.get(name)
			if node is None:
				raise RuntimeError(f"Node lookup failed for '{name}' on {gns3_ip}")
			target = resolve_console_target(node, gns3_server_ip=gns3_ip)
			if target is None:
				raise RuntimeError(f"Node '{name}' has no telnet console to run scripts")
			host, port = target
			return NodeRun(name=name, node_id=node["node_id"], host=host, port=port, command=command)

		dhcp_nodes, server_nodes, client_nodes = categorize_nodes(nodes)

		server_runs = [
			_to_run(name, REMOTE_DHCP_SCRIPT)
			for name in dhcp_nodes
		] + [
			_to_run(name, REMOTE_SERVER_SCRIPT)
			for name in server_nodes
		]

		client_runs = [
			_to_run(name, REMOTE_CLIENT_SCRIPT)
			for name in client_nodes
		]

		run_scripts(server_runs, "server")
		run_scripts(client_runs, "client")
	finally:
		client.session.close()


def main() -> None:
	settings = APISettings()  # type: ignore[call-arg]
	project = load_project_info(PROJECT_NAME)
	targets = expand_targets(TARGET_GNS3_SERVERS)

	if not targets:
		raise SystemExit("No GNS3 server targets were provided.")

	print(f"Executing scenario for project '{project.name}' ({project.project_id})")
	print(f"Targets: {', '.join(targets)}")

	max_workers = max(1, min(SERVER_CONCURRENCY, len(targets)))
	failures: List[str] = []
	with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as executor:
		future_map = {
			executor.submit(process_server, ip, project, settings): ip
			for ip in targets
		}
		for future in concurrent.futures.as_completed(future_map):
			ip = future_map[future]
			try:
				future.result()
			except Exception as exc:
				error_message = f"[WARN] Skipping GNS3 server {ip}: {exc}"
				print(error_message)
				failures.append(error_message)

	if failures:
		print("\nCompleted with warnings:")
		for message in failures:
			print(f"  - {message}")

	print("Done.")


if __name__ == "__main__":
	main()

