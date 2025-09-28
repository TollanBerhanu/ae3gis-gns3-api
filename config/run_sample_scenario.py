#!/usr/bin/env python3
import requests
from dataclasses import dataclass
from typing import Dict, List, Tuple

# ========= CONFIG (edit as needed) =========
API_BASE = "http://127.0.0.1:8000"
BUILD_URL = f"{API_BASE}/scenario/build"
SCRIPTS_URL = f"{API_BASE}/scripts/push"

GNS3_BASE_URL = "http://192.168.56.101"
GNS3_SERVER_IP = "192.168.56.101"
PROJECT_NAME = "ae3gis-scenario-builder-test"
PROJECT_ID = "8b26f4d4-5445-4e86-86a0-d46944d8e85b"

# Template IDs (single source of truth)
TEMPLATES: Dict[str, str] = {
    "test-client": "df206cef-efd5-45dc-93d4-1f94c31cfb16",
    "nginx-server": "65ac4263-d944-4b7d-a068-5a836b29319f",
    "openvswitch": "e257b341-cec3-4076-a239-181c5101ff37",
    "dhcp": "3cecbf43-5f8b-4678-97f3-6ace71b02853",
}

# How many scenarios (tiles) to create and how they are laid out
NUM_SCENARIOS = 24
SCENARIOS_PER_ROW = 4             # how many tiles per row
TILE_WIDTH = 900                  # px between scenarios horizontally
TILE_HEIGHT = 500                 # px between scenarios vertically
CANVAS_TOP_LEFT = (-1500, -1000)  # where the first scenario starts

# Clients layout inside each scenario (tile)
CLIENTS_PER_SCENARIO = 13
CLIENTS_PER_ROW = 13
NODE_SPACING_X = 50
NODE_SPACING_Y = 50

# Special node offsets inside a tile (relative to tile origin)
SWITCH_OFFSET = (300, -140)
DHCP_OFFSET = (600, -140)
SERVER_OFFSET = (300, -250)

# Scripts (local to your machine)
SERVER_SCRIPT = "./run_server.sh"
DHCP_SCRIPT = "./run_dhcp.sh"
CLIENT_SCRIPT = "./run_http.sh"
SCRIPTS_CONCURRENCY = 5  # the API may still run uploads concurrently; our calls remain sequential

ID_PAD = 2  # zero pad for names like 01, 02, ...
START_AT = 1
# ===========================================


@dataclass
class Tile:
    col: int
    row: int
    x: int
    y: int


def tile_for_index(idx: int) -> Tile:
    col = idx % SCENARIOS_PER_ROW
    row = idx // SCENARIOS_PER_ROW
    x = CANVAS_TOP_LEFT[0] + col * TILE_WIDTH
    y = CANVAS_TOP_LEFT[1] + row * TILE_HEIGHT
    return Tile(col, row, x, y)


def make_clients(tile: Tile, start_id: int) -> Tuple[List[Dict], List[str], int]:
    nodes = []
    names = []
    next_id = start_id
    for i in range(CLIENTS_PER_SCENARIO):
        r = i // CLIENTS_PER_ROW
        c = i % CLIENTS_PER_ROW
        x = tile.x + c * NODE_SPACING_X
        y = tile.y + r * NODE_SPACING_Y
        name = f"Client-{next_id:0{ID_PAD}d}"
        nodes.append({
            "name": name,
            "template_id": TEMPLATES["test-client"],
            "x": x,
            "y": y
        })
        names.append(name)
        next_id += 1
    return nodes, names, next_id


def make_special_nodes(tile: Tile, scenario_idx: int) -> Tuple[List[Dict], Dict[str, str]]:
    sid = scenario_idx + START_AT
    sw_name = f"OpenvSwitch-{sid:0{ID_PAD}d}"
    dhcp_name = f"DHCP-{sid:0{ID_PAD}d}"
    server_name = f"Server-{sid:0{ID_PAD}d}"
    sx, sy = SWITCH_OFFSET
    dx, dy = DHCP_OFFSET
    vx, vy = SERVER_OFFSET

    nodes = [
        {"name": sw_name, "template_id": TEMPLATES["openvswitch"], "x": tile.x + sx, "y": tile.y + sy},
        {"name": dhcp_name, "template_id": TEMPLATES["dhcp"], "x": tile.x + dx, "y": tile.y + dy},
        {"name": server_name, "template_id": TEMPLATES["nginx-server"], "x": tile.x + vx, "y": tile.y + vy},
    ]
    return nodes, {"switch": sw_name, "dhcp": dhcp_name, "server": server_name}


def make_links(client_names: List[str], switch_name: str, dhcp_name: str, server_name: str) -> List[Dict]:
    links = []
    # clients to switch (client adapter 0 -> switch adapters 1..n)
    for i, cname in enumerate(client_names, start=1):
        links.append({
            "nodes": [
                {"node_id": cname, "adapter_number": 0, "port_number": 0},
                {"node_id": switch_name, "adapter_number": i, "port_number": 0},
            ]
        })
    # server to switch (next adapter)
    next_adapter = len(client_names) + 1
    links.append({
        "nodes": [
            {"node_id": server_name, "adapter_number": 0, "port_number": 0},
            {"node_id": switch_name, "adapter_number": next_adapter, "port_number": 0},
        ]
    })
    # dhcp to switch (next adapter)
    links.append({
        "nodes": [
            {"node_id": dhcp_name, "adapter_number": 0, "port_number": 0},
            {"node_id": switch_name, "adapter_number": next_adapter + 1, "port_number": 0},
        ]
    })
    return links


def build_payload(tile: Tile, scenario_idx: int, next_client_id: int) -> Tuple[Dict, List[str], Dict[str, str], int]:
    client_nodes, client_names, after_id = make_clients(tile, next_client_id)
    special_nodes, special_names = make_special_nodes(tile, scenario_idx)
    links = make_links(client_names, special_names["switch"], special_names["dhcp"], special_names["server"])

    payload = {
        "base_url": GNS3_BASE_URL,
        "start_nodes": True,
        "scenario": {
            "gns3_server_ip": GNS3_SERVER_IP,
            "project_name": PROJECT_NAME,
            "project_id": PROJECT_ID,
            "templates": TEMPLATES,  # do not repeat IDs elsewhere
            "nodes": client_nodes + special_nodes,
            "links": links,
        }
    }
    return payload, client_names, special_names, after_id


def post_json(url: str, data: Dict) -> Dict:
    r = requests.post(url, json=data, timeout=360)
    r.raise_for_status()
    return r.json() if r.headers.get("content-type", "").startswith("application/json") else {"text": r.text}


def push_script(node_name: str, local_path: str, remote_path: str, shell: str = "sh", timeout: int = 10) -> None:
    payload = {
        "scripts": [{
            "node_name": node_name,
            "local_path": local_path,
            "remote_path": remote_path,
            "run_after_upload": True,
            "executable": True,
            "overwrite": True,
            "run_timeout": timeout,
            "shell": shell
        }],
        "host_override": GNS3_BASE_URL,
        "concurrency": SCRIPTS_CONCURRENCY
    }
    post_json(SCRIPTS_URL, payload)


def push_batch_scripts(node_names: List[str], local_path: str, remote_path: str, shell: str = "sh", timeout: int = 10) -> None:
    scripts = [{
        "node_name": n,
        "local_path": local_path,
        "remote_path": remote_path,
        "run_after_upload": True,
        "executable": True,
        "overwrite": True,
        "run_timeout": timeout,
        "shell": shell
    } for n in node_names]
    payload = {
        "scripts": scripts,
        "host_override": GNS3_BASE_URL,
        "concurrency": SCRIPTS_CONCURRENCY
    }
    post_json(SCRIPTS_URL, payload)


def main():
    next_client_id = START_AT

    with requests.Session() as _:
        for scenario_idx in range(NUM_SCENARIOS):
            tile = tile_for_index(scenario_idx)
            build_body, client_names, special_names, next_client_id = build_payload(tile, scenario_idx, next_client_id)

            print(f"Building scenario {scenario_idx + 1}/{NUM_SCENARIOS} at tile ({tile.col},{tile.row}) origin=({tile.x},{tile.y})")
            post_json(BUILD_URL, build_body)

            # Sequential script pushes (order matters)
            print("  Pushing server script...")
            push_script(special_names["server"], SERVER_SCRIPT, "/run_server.sh")
            print("  Pushing DHCP script...")
            push_script(special_names["dhcp"], DHCP_SCRIPT, "/usr/run_dhcp.sh")
            print("  Pushing client scripts...")
            push_batch_scripts(client_names, CLIENT_SCRIPT, "/usr/run_http.sh")

    print("Done.")


if __name__ == "__main__":
    main()