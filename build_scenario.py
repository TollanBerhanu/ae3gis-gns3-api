#!/usr/bin/env python3
import argparse
import json
import os
import re
import sys
import time
import requests

# ---------- GNS3 HTTP helpers (modeled after your reference script) ----------
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

def add_node_from_template(session, base_url, project_id, template_id, name, x, y):
    url = f"{base_url}/v2/projects/{project_id}/templates/{template_id}"
    payload = {"x": x, "y": y, "name": name}
    node = gns3_post(session, url, json=payload)
    node_id = node.get("node_id")
    if not node_id:
        raise SystemExit(f"[ERROR] Failed to create node '{name}' from template {template_id}: {node}")
    return node

def create_link(session, base_url, project_id, a, b):
    """
    a, b are dicts with: node_id, adapter_number, port_number
    """
    url = f"{base_url}/v2/projects/{project_id}/links"
    payload = {"nodes": [a, b]}
    return gns3_post(session, url, json=payload)

def start_node(session, base_url, project_id, node_id):
    url = f"{base_url}/v2/projects/{project_id}/nodes/{node_id}/start"
    try:
        gns3_post(session, url)
        return True
    except requests.HTTPError as e:
        # Some nodes (e.g., Ethernet/OVS switch) may auto-start or skip /start
        print(f"[WARN] Could not start node {node_id}: {e}", file=sys.stderr)
        return False

# ---------- Utilities for mapping placeholders like NODE_OVS_IT ----------
NON_ALNUM_RE = re.compile(r"[^A-Za-z0-9]+")
def make_base_alias(name: str) -> str:
    base = NON_ALNUM_RE.sub("_", name).strip("_").upper()
    return base

def alias_variants(name: str):
    """
    Generate a few tolerant variants so links can reference NODE_* tokens flexibly.
    e.g., 'OpenvSwitch-IT' -> NODE_OPENVSWITCH_IT and NODE_OVS_IT
          'IPTables-Firewall' -> NODE_IPTABLES_FIREWALL and NODE_FIREWALL
    """
    base = make_base_alias(name)
    variants = {f"NODE_{base}"}

    # OPENVSWITCH -> OVS
    if "OPENVSWITCH" in base:
        variants.add(f"NODE_{base.replace('OPENVSWITCH', 'OVS')}")

    # If FIREWALL appears, also allow plain FIREWALL
    if "FIREWALL" in base:
        variants.add("NODE_FIREWALL")

    # Allow collapsing IPTABLES_ prefix for friendliness
    if base.startswith("IPTABLES_"):
        variants.add(f"NODE_{base.replace('IPTABLES_', '')}")

    return variants

def resolve_link_endpoint(token_or_name, name_to_id, alias_to_id):
    """
    Accepts either a real UUID node_id, a placeholder like NODE_X, or a node name.
    """
    if not token_or_name:
        raise SystemExit("[ERROR] Link endpoint missing node reference")

    # If it's a UUID-like id already created:
    if isinstance(token_or_name, str) and token_or_name.count("-") >= 4 and token_or_name.startswith(tuple("0123456789abcdef")):
        return token_or_name

    # Placeholder like NODE_SOMETHING
    if isinstance(token_or_name, str) and token_or_name.upper().startswith("NODE_"):
        if token_or_name in alias_to_id:
            return alias_to_id[token_or_name]
        raise SystemExit(f"[ERROR] Could not resolve link placeholder '{token_or_name}' to a created node")

    # Otherwise treat as name
    if token_or_name in name_to_id:
        return name_to_id[token_or_name]

    raise SystemExit(f"[ERROR] Could not resolve link endpoint '{token_or_name}'. "
                     f"Known names: {list(name_to_id.keys())}")

# ---------- Main workflow ----------
def main():
    ap = argparse.ArgumentParser(description="Build a GNS3 topology from scenario.json")
    ap.add_argument("--scenario", default="scenario.json", help="Path to scenario JSON")
    ap.add_argument("--server", help="Override GNS3 base URL, e.g. http://172.16.194.129:80")
    ap.add_argument("--user", help="Basic auth username (if GNS3 API requires auth)")
    ap.add_argument("--password", help="Basic auth password (if GNS3 API requires auth)")
    ap.add_argument("--start", action="store_true", help="Start nodes after creation")
    args = ap.parse_args()

    # Load scenario
    if not os.path.isfile(args.scenario):
        raise SystemExit(f"[ERROR] Scenario file not found: {args.scenario}")
    with open(args.scenario, "r", encoding="utf-8") as f:
        scenario = json.load(f)

    # Determine base_url
    if args.server:
        base_url = args.server.rstrip("/")
    else:
        ip = scenario.get("gns3_server_ip")
        if not ip:
            raise SystemExit("[ERROR] 'gns3_server_ip' missing in scenario.json (or use --server)")
        # default to HTTP on port 80 unless the value already contains a scheme/port
        if ip.startswith("http://") or ip.startswith("https://"):
            base_url = ip.rstrip("/")
        else:
            base_url = f"http://{ip}:80"

    # Prepare HTTP session
    session = requests.Session()
    session.headers.update({"Accept": "application/json", "Content-Type": "application/json"})
    if args.user and args.password:
        session.auth = (args.user, args.password)

    # Project
    project_id = scenario.get("project_id")
    project_name = scenario.get("project_name")
    if not project_id:
        if not project_name:
            raise SystemExit("[ERROR] Provide 'project_id' or 'project_name' in scenario.json")
        project_id = find_project_id(session, base_url, project_name)
    print(f"[INFO] Using project '{project_name or '(id)'}' ({project_id}) at {base_url}")

    # Create nodes
    created = []
    name_to_id = {}
    alias_to_id = {}

    nodes = scenario.get("nodes", [])
    if not nodes:
        raise SystemExit("[ERROR] No 'nodes' list in scenario.json")

    for idx, n in enumerate(nodes, start=1):
        name = n["name"]
        template_id = n.get("template_id")
        if not template_id:
            # Optional alt inputs: template_name or template_key in scenario['templates']
            t_key = n.get("template_key")
            t_name = n.get("template_name")
            if t_key and "templates" in scenario and t_key in scenario["templates"]:
                template_id = scenario["templates"][t_key]
            elif t_name:
                # If a template name is given, look it up
                templates = gns3_get(session, f"{base_url}/v2/templates")
                by_name = {t["name"]: t["template_id"] for t in templates}
                if t_name not in by_name:
                    raise SystemExit(f"[ERROR] Template named '{t_name}' not found on server")
                template_id = by_name[t_name]
            else:
                raise SystemExit(f"[ERROR] Node '{name}' missing template_id/template_key/template_name")

        x = int(n.get("x", 0))
        y = int(n.get("y", 0))

        node = add_node_from_template(session, base_url, project_id, template_id, name=name, x=x, y=y)
        node_id = node["node_id"]
        created.append(node)
        name_to_id[name] = node_id

        # Build tolerant alias entries so links can reference NODE_* placeholders
        for alias in alias_variants(name):
            alias_to_id.setdefault(alias, node_id)

        print(f"[INFO] Created node '{name}' ({node_id}) at ({x},{y})")

        time.sleep(0.05)  # small pacing

    # Create links
    links = scenario.get("links", [])
    if not links:
        print("[INFO] No 'links' in scenario.json; skipping link creation")
    else:
        for i, L in enumerate(links, start=1):
            # Each link must provide exactly two endpoints in L["nodes"]
            if "nodes" not in L or not isinstance(L["nodes"], list) or len(L["nodes"]) != 2:
                raise SystemExit(f"[ERROR] Link #{i} must contain two 'nodes' endpoints")
            a_in = L["nodes"][0]
            b_in = L["nodes"][1]

            # Accept either {node_id:'NODE_*'} or {name:'Workstation-1'} per endpoint
            a_node_ref = a_in.get("node_id") or a_in.get("name")
            b_node_ref = b_in.get("node_id") or b_in.get("name")

            a_id = resolve_link_endpoint(a_node_ref, name_to_id, alias_to_id)
            b_id = resolve_link_endpoint(b_node_ref, name_to_id, alias_to_id)

            a = {
                "node_id": a_id,
                "adapter_number": int(a_in.get("adapter_number", 0)),
                "port_number": int(a_in.get("port_number", 0)),
            }
            b = {
                "node_id": b_id,
                "adapter_number": int(b_in.get("adapter_number", 0)),
                "port_number": int(b_in.get("port_number", 0)),
            }

            resp = create_link(session, base_url, project_id, a, b)
            print(f"[INFO] Created link #{i}: {a_id}({a['adapter_number']}/{a['port_number']}) "
                  f"<-> {b_id}({b['adapter_number']}/{b['port_number']}); link_id={resp.get('link_id')}")
            time.sleep(0.05)

    # Optionally start nodes
    if args.start:
        started = 0
        for node in created:
            if start_node(session, base_url, project_id, node["node_id"]):
                started += 1
        print(f"[INFO] Started {started}/{len(created)} nodes")

    print("[DONE] Topology creation complete.")

if __name__ == "__main__":
    main()
