#!/usr/bin/env python3
import argparse
import sys
import time
import requests

def gns3_get(session, url):
    r = session.get(url)
    r.raise_for_status()
    return r.json()

def gns3_post(session, url, json=None):
    r = session.post(url, json=json or {})
    r.raise_for_status()
    return r.json() if r.text else {}

def find_project_id(session, base_url, project_name):
    projects = gns3_get(session, f"{base_url}/v2/projects")
    for p in projects:
        if p.get("name") == project_name:
            return p["project_id"]
    raise SystemExit(f"[ERROR] Project named '{project_name}' not found at {base_url}/v2/projects")

def get_template_map(session, base_url):
    templates = gns3_get(session, f"{base_url}/v2/templates")
    print(f"[INFO] Found {len(templates)} templates on server {base_url}")
    # map by name (exact match) -> id
    return {t.get("name"): t.get("template_id") for t in templates}

def ensure_template(session, base_url, template_map, name):
    if name not in template_map:
        available = ", ".join(sorted(template_map.keys()))
        raise SystemExit(f"[ERROR] Template '{name}' not found.\nAvailable templates: {available}")
    return template_map[name]

def add_node_from_template(session, base_url, project_id, template_id, name, x, y):
    url = f"{base_url}/v2/projects/{project_id}/templates/{template_id}"
    payload = {"compute_id": "local" ,"x": x, "y": y, "name": name}
    node = gns3_post(session, url, json=payload)
    node_id = node.get("node_id")
    if not node_id:
        raise SystemExit(f"[ERROR] Failed to create node from template {template_id}: {node}")
    return node

def link_to_switch(session, base_url, project_id, switch_id, device_id, switch_port, device_adapter=0, device_port=0, switch_adapter=0):
    url = f"{base_url}/v2/projects/{project_id}/links"
    payload = {
        "nodes": [
            {"node_id": device_id, "adapter_number": device_adapter, "port_number": device_port},
            {"node_id": switch_id, "adapter_number": switch_adapter, "port_number": switch_port},
        ]
    }
    return gns3_post(session, url, json=payload)

def start_node(session, base_url, project_id, node_id):
    url = f"{base_url}/v2/projects/{project_id}/nodes/{node_id}/start"
    try:
        gns3_post(session, url)
        return True
    except requests.HTTPError as e:
        # Some nodes (e.g., Ethernet switch) may auto-start or not support /start; don't hard-fail.
        print(f"[WARN] Could not start node {node_id}: {e}", file=sys.stderr)
        return False

def main():
    parser = argparse.ArgumentParser(description="Create a simple topology in GNS3 and start nodes.")
    parser.add_argument("--server", default="http://172.16.194.129:80", help="GNS3 server base URL")
    parser.add_argument("--project", default="Demo Project", help="Existing GNS3 project name")
    parser.add_argument("--firewalls", type=int, default=2, help="Number of firewall nodes")
    parser.add_argument("--workstations", type=int, default=3, help="Number of workstation nodes")
    parser.add_argument("--firewall-template", default="Firewall Docker", help="Template name for firewall")
    parser.add_argument("--workstation-template", default="Workstation Docker", help="Template name for workstation")
    parser.add_argument("--switch-template", default="Ethernet switch", help="Template name for switch")
    parser.add_argument("--x0", type=int, default=100, help="Starting X coordinate")
    parser.add_argument("--y0", type=int, default=100, help="Starting Y coordinate")
    parser.add_argument("--xstep", type=int, default=180, help="X spacing between nodes")
    parser.add_argument("--ystep", type=int, default=130, help="Y spacing between rows")
    parser.add_argument("--per-row", type=int, default=6, help="Devices per row")
    parser.add_argument("--user", help="Basic auth username (if your GNS3 API requires auth)")
    parser.add_argument("--password", help="Basic auth password (if your GNS3 API requires auth)")
    args = parser.parse_args()

    base_url = args.server.rstrip("/")

    # Prepare HTTP session
    session = requests.Session()
    # if args.user and args.password:
    #     session.auth = (args.user, args.password)
    # session.headers.update({"Accept": "application/json", "Content-Type": "application/json"})

    # 1) Find project
    project_id = find_project_id(session, base_url, args.project)
    print(f"[INFO] Using project '{args.project}' ({project_id})")

    # 2) Lookup templates
    tmap = get_template_map(session, base_url)
    fw_tid = ensure_template(session, base_url, tmap, args.firewall_template)
    ws_tid = ensure_template(session, base_url, tmap, args.workstation_template)
    sw_tid = ensure_template(session, base_url, tmap, args.switch_template)

    # 3) Create the switch (top/center-ish)
    switch_x = args.x0 + (args.xstep * min(args.per_row, args.firewalls + args.workstations)) // 2
    switch_y = args.y0
    switch_node = add_node_from_template(
        session, base_url, project_id, sw_tid, name="Core-Switch", x=switch_x, y=switch_y
    )
    switch_id = switch_node["node_id"]
    print(f"[INFO] Created switch {switch_id} at ({switch_x},{switch_y})")

    # 4) Create firewall + workstation nodes with a simple grid layout
    created_nodes = []  # list of (node_id, name)
    current_index = 0
    def grid_pos(idx):
        row = idx // args.per_row
        col = idx % args.per_row
        x = args.x0 + col * args.xstep
        y = args.y0 + args.ystep * (row + 1)  # +1 so they appear below the switch row
        return x, y

    # Firewalls
    for i in range(args.firewalls):
        name = f"FW-{i+1}"
        x, y = grid_pos(current_index)
        n = add_node_from_template(session, base_url, project_id, fw_tid, name=name, x=x, y=y)
        created_nodes.append((n["node_id"], name))
        print(f"[INFO] Created firewall {name} ({n['node_id']}) at ({x},{y})")
        current_index += 1

    # Workstations
    for i in range(args.workstations):
        name = f"WS-{i+1}"
        x, y = grid_pos(current_index)
        n = add_node_from_template(session, base_url, project_id, ws_tid, name=name, x=x, y=y)
        created_nodes.append((n["node_id"], name))
        print(f"[INFO] Created workstation {name} ({n['node_id']}) at ({x},{y})")
        current_index += 1

    # 5) Link all devices to the switch
    #    We’ll connect device adapter 0,port 0 to switch adapter 0,port N
    switch_port = 0
    for node_id, name in created_nodes:
        link = link_to_switch(session, base_url, project_id, switch_id, node_id, switch_port)
        print(f"[INFO] Linked {name} ({node_id}) <-> Switch({switch_id}) on switch port {switch_port} (link_id={link.get('link_id')})")
        switch_port += 1
        time.sleep(0.05)  # tiny delay to avoid overwhelming the server

    # 6) Start nodes (switch may auto-start or ignore /start)
    started = 0
    for node_id, name in created_nodes + [(switch_id, "Core-Switch")]:
        if start_node(session, base_url, project_id, node_id):
            started += 1
            print(f"[INFO] Started {name} ({node_id})")

    print(f"[DONE] Created {len(created_nodes)} devices, linked all to switch, started {started} nodes.")

if __name__ == "__main__":
    main()
