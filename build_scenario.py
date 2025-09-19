#!/usr/bin/env python3
import argparse
import json
import os
import re
import sys
import time
import requests

# HTTP helper functions
def gns3_get(s, url):
    r = s.get(url)
    r.raise_for_status()
    return r.json()

def gns3_post(s, url, json=None):
    r = s.post(url, json=json or {})
    r.raise_for_status()
    return r.json() if r.text else {}

# Find Project ID by name
def find_project_id(s, base_url, project_name):
    for p in gns3_get(s, f"{base_url}/v2/projects"):
        if p.get("name") == project_name:
            return p["project_id"]
    raise SystemExit(f"[ERROR] Project named '{project_name}' not found")

# Add Node / Create Link
def add_node_from_template(s, base_url, project_id, template_id, name, x, y):
    url = f"{base_url}/v2/projects/{project_id}/templates/{template_id}"
    payload = {"x": x, "y": y, "name": name}
    node = gns3_post(s, url, json=payload)
    if "node_id" not in node:
        raise SystemExit(f"[ERROR] Failed to create node '{name}': {node}")
    return node

def get_node(s, base_url, project_id, node_id):
    return gns3_get(s, f"{base_url}/v2/projects/{project_id}/nodes/{node_id}")

def create_link(s, base_url, project_id, a, b):
    url = f"{base_url}/v2/projects/{project_id}/links"
    payload = {"nodes": [a, b]}
    return gns3_post(s, url, json=payload)

def start_node(s, base_url, project_id, node_id):
    try:
        gns3_post(s, f"{base_url}/v2/projects/{project_id}/nodes/{node_id}/start")
        return True
    except requests.HTTPError as e:
        # Some nodes (e.g., switches) may not need /start
        print(f"[WARN] Could not start node {node_id}: {e}", file=sys.stderr)
        return False

# Placeholder aliasing for links
NON_ALNUM = re.compile(r"[^A-Za-z0-9]+")
def _alias_base(name): return NON_ALNUM.sub("_", name).strip("_").upper()

def alias_variants(name):
    base = _alias_base(name)
    vs = {f"NODE_{base}"}
    if "OPENVSWITCH" in base:
        vs.add(f"NODE_{base.replace('OPENVSWITCH','OVS')}")
    if "FIREWALL" in base:
        vs.add("NODE_FIREWALL")
    if base.startswith("IPTABLES_"):
        vs.add(f"NODE_{base.replace('IPTABLES_','')}")
    return vs

def resolve_endpoint(ref, name_to_id, alias_to_id):
    # Allow real UUIDs, NODE_* placeholders, or human names
    if isinstance(ref, str) and ref.upper().startswith("NODE_"):
        if ref in alias_to_id: return alias_to_id[ref]
        raise SystemExit(f"[ERROR] Unresolved link placeholder '{ref}'")
    if isinstance(ref, str) and ref in name_to_id:
        return name_to_id[ref]
    if isinstance(ref, str) and ref.count("-") >= 4:  # uuid-ish
        return ref
    raise SystemExit(f"[ERROR] Unresolved link endpoint '{ref}'")

# -------------------- Build Config file --------------------
def make_config_record(project_name, project_id, nodes_detail, links_detail):
    cfg = {
        "project_name": project_name or "",
        "project_id": project_id,
        "nodes": [],
        "links": []
    }
    # nodes
    for nd in nodes_detail:
        props = nd.get("properties", {}) or {}
        cfg["nodes"].append({
            "name": nd.get("name"),
            "node_id": nd.get("node_id"),
            "template_id": nd.get("template_id"),
            "compute_id": nd.get("compute_id", "local"),
            "console": nd.get("console"),
            "console_host": nd.get("console_host"),
            "console_type": nd.get("console_type"),
            "ports": [
                {
                    "adapter_number": p.get("adapter_number", 0),
                    "port_number": p.get("port_number", 0)
                } for p in (nd.get("ports") or [])
            ],
            "properties": {
                "adapters": props.get("adapters"),
                "aux": props.get("aux")
            },
            "status": nd.get("status"),
            "x": nd.get("x", 0),
            "y": nd.get("y", 0)
        })

    # links
    for lk in links_detail:
        cfg["links"].append({
            "link_id": lk.get("link_id"),
            "link_type": lk.get("link_type", "ethernet"),
            "nodes": [
                {
                    "node_id": n.get("node_id"),
                    "adapter_number": n.get("adapter_number", 0),
                    "port_number": n.get("port_number", 0)
                } for n in lk.get("nodes", [])
            ]
        })
    return cfg

# -------------------- Main --------------------
def main():
    ap = argparse.ArgumentParser(description="Build GNS3 topology from scenario.json and emit config.json")
    ap.add_argument("--scenario", default="scenario.json", help="Scenario JSON path")
    ap.add_argument("--server", help="Override GNS3 base URL, e.g. http://172.16.194.129:80")
    ap.add_argument("--user", help="HTTP Basic user (if required)")
    ap.add_argument("--password", help="HTTP Basic password (if required)")
    ap.add_argument("--start", action="store_true", help="Start nodes after creation")
    ap.add_argument("--config-out", default="config.generated.json", help="Where to write the config file")
    args = ap.parse_args()

    if not os.path.isfile(args.scenario):
        raise SystemExit(f"[ERROR] Scenario file not found: {args.scenario}")
    with open(args.scenario, "r", encoding="utf-8") as f:
        scenario = json.load(f)

    # Base URL
    if args.server:
        base_url = args.server.rstrip("/")
    else:
        ip = scenario.get("gns3_server_ip")
        if not ip:
            raise SystemExit("[ERROR] 'gns3_server_ip' missing (or pass --server)")
        base_url = ip if ip.startswith("http") else f"http://{ip}:80"
        base_url = base_url.rstrip("/")

    # Session
    s = requests.Session()
    s.headers.update({"Accept": "application/json", "Content-Type": "application/json"})
    if args.user and args.password:
        s.auth = (args.user, args.password)

    # Project resolution
    project_id = scenario.get("project_id")
    project_name = scenario.get("project_name")
    if not project_id:
        if not project_name:
            raise SystemExit("[ERROR] Provide 'project_id' or 'project_name' in scenario.json")
        project_id = find_project_id(s, base_url, project_name)
    print(f"[INFO] Project: {project_name or '(id)'} ({project_id}) @ {base_url}")

    # Node creation
    created_nodes = []
    name_to_id = {}
    alias_to_id = {}

    nodes_spec = scenario.get("nodes", [])
    if not nodes_spec:
        raise SystemExit("[ERROR] No 'nodes' array in scenario")

    # Optional templates map for scenario key lookups
    templates_map = scenario.get("templates", {}) or {}

    for spec in nodes_spec:
        name = spec["name"]
        x, y = int(spec.get("x", 0)), int(spec.get("y", 0))

        template_id = spec.get("template_id")
        if not template_id:
            t_key = spec.get("template_key")
            t_name = spec.get("template_name")
            if t_key and t_key in templates_map:
                template_id = templates_map[t_key]
            elif t_name:
                # Lookup template by name from server
                t_by_name = {t["name"]: t["template_id"] for t in gns3_get(s, f"{base_url}/v2/templates")}
                if t_name not in t_by_name:
                    raise SystemExit(f"[ERROR] Template '{t_name}' not found on server")
                template_id = t_by_name[t_name]
            else:
                raise SystemExit(f"[ERROR] Node '{name}' missing template_id/template_key/template_name")

        node = add_node_from_template(s, base_url, project_id, template_id, name, x, y)
        created_nodes.append(node)
        name_to_id[name] = node["node_id"]
        for a in alias_variants(name):
            alias_to_id.setdefault(a, node["node_id"])
        print(f"[INFO] Created node '{name}' ({node['node_id']}) at ({x},{y})")
        time.sleep(0.05)

    # Link creation
    created_links = []
    links_spec = scenario.get("links", []) or []
    for i, LK in enumerate(links_spec, start=1):
        if "nodes" not in LK or len(LK["nodes"]) != 2:
            raise SystemExit(f"[ERROR] Link #{i} must specify two endpoints in 'nodes'")
        a_in, b_in = LK["nodes"][0], LK["nodes"][1]

        a_ref = a_in.get("node_id") or a_in.get("name")
        b_ref = b_in.get("node_id") or b_in.get("name")
        a_id = resolve_endpoint(a_ref, name_to_id, alias_to_id)
        b_id = resolve_endpoint(b_ref, name_to_id, alias_to_id)

        a = {"node_id": a_id,
             "adapter_number": int(a_in.get("adapter_number", 0)),
             "port_number": int(a_in.get("port_number", 0))}
        b = {"node_id": b_id,
             "adapter_number": int(b_in.get("adapter_number", 0)),
             "port_number": int(b_in.get("port_number", 0))}

        link_resp = create_link(s, base_url, project_id, a, b)
        created_links.append(link_resp)
        print(f"[INFO] Created link #{i} -> link_id={link_resp.get('link_id')}")
        time.sleep(0.05)

    # Optionally start nodes
    if args.start:
        for n in created_nodes:
            start_node(s, base_url, project_id, n["node_id"])

    # Refresh details (so config captures final console/status/ports)
    nodes_detail = []
    for n in created_nodes:
        nd = get_node(s, base_url, project_id, n["node_id"])
        nodes_detail.append(nd)
    # Pull full link list for this project (captures any implicit fields)
    links_detail = gns3_get(s, f"{base_url}/v2/projects/{project_id}/links")

    # Build and write config
    cfg = make_config_record(project_name, project_id, nodes_detail, links_detail)
    with open(args.config_out, "w", encoding="utf-8") as f:
        json.dump(cfg, f, indent=4)
    print(f"[INFO] Wrote config file -> {args.config_out}")
    print("[DONE] Topology + config generation complete.")

if __name__ == "__main__":
    main()
