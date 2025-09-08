#!/usr/bin/env python3
"""
Cross-platform DHCP orchestrator for GNS3 Linux container nodes using Telnet.

- Reads config.generated.json (or config.json) and ip_plan.json (for fallbacks and firewall static IPs).
- For *components* (workstations, firewalls; skips switches), it:
    * Brings interfaces up
    * Tries DHCP with dhclient -> udhcpc -> dhcpcd
    * If no DHCP client present or request fails, falls back to static from ip_plan.json
- Detects firewall nodes by name and applies iptables rules:
    * Allow ICMP
    * Allow DHCP (UDP 67/68)
    * Allow established/related
    * Heuristic "scan guard" to throttle/drop Nmap-style bursts
- Updates address_book.generated.json with discovered/assigned IPs.

Run from Windows, Linux, or macOS. Only standard library is used.
"""

import argparse
import json
import re
import telnetlib
import time
import uuid
from typing import Dict, Any

PROMPT_TIMEOUT = 5.0
CMD_TIMEOUT = 30.0

def info(msg): print(f"[INFO] {msg}", flush=True)
def warn(msg): print(f"[WARN] {msg}", flush=True)
def err(msg):  print(f"[ERROR] {msg}", flush=True)

def is_switch(name: str) -> bool:
    n = name.lower()
    return ("switch" in n) or ("openvswitch" in n) or (n.startswith("ovs-"))

def is_firewall(name: str) -> bool:
    return "firewall" in name.lower()

def pick_console_host(node: Dict[str, Any], override_host: str|None) -> str:
    if override_host:
        return override_host
    h = node.get("console_host") or "127.0.0.1"
    if h == "0.0.0.0":
        return override_host or "127.0.0.1"
    return h

class TelnetSession:
    def __init__(self, host: str, port: int, timeout=10.0):
        self.host = host; self.port = port; self.timeout = timeout
        self.tn = None

    def connect(self):
        info(f"Telnet connect {self.host}:{self.port}")
        self.tn = telnetlib.Telnet(self.host, self.port, timeout=self.timeout)
        time.sleep(0.25)

    def close(self):
        try:
            if self.tn:
                self.tn.write(b"exit\n")
        except Exception:
            pass
        try:
            if self.tn:
                self.tn.close()
        except Exception:
            pass

    def run(self, command: str, timeout: float = CMD_TIMEOUT) -> tuple[int, str]:
        token = f"__END__{uuid.uuid4().hex}__"
        wrapped = f"{command}; rc=$?; echo {token} $rc\n"
        self.tn.write(wrapped.encode("utf-8", "ignore"))

        buf = b""
        end_pattern = token.encode("utf-8")
        end_time = time.time() + timeout
        while time.time() < end_time:
            try:
                chunk = self.tn.read_eager()
            except EOFError:
                break
            if chunk:
                buf += chunk
                if end_pattern in buf:
                    break
            else:
                time.sleep(0.05)

        text = buf.decode("utf-8", "ignore")
        m = re.search(rf"{re.escape(token)}\s+(\d+)", text)
        rc = int(m.group(1)) if m else 0
        return rc, text

def parse_ipv4_from_ip_addr(output: str) -> str|None:
    m = re.search(r"inet\s+(\d+\.\d+\.\d+\.\d+)/(\\d+)", output)
    if not m:
        return None
    ip = m.group(1); prefix = m.group(2)
    return f"{ip}/{prefix}"

def parse_gw_from_ip_route(output: str, ifname: str) -> str|None:
    for line in output.splitlines():
        if "default via" in line and f"dev {ifname}" in line:
            m = re.search(r"default\\s+via\\s+(\\d+\\.\\d+\\.\\d+\\.\\d+)", line)
            if m:
                return m.group(1)
    m = re.search(r"default\\s+via\\s+(\\d+\\.\\d+\\.\\d+\\.\\d+)", output)
    return m.group(1) if m else None

def configure_firewall(ts: TelnetSession):
    cmds = [
        "sysctl -w net.ipv4.ip_forward=1",
        "iptables -F; iptables -X; iptables -t nat -F; iptables -t mangle -F",
        "iptables -P INPUT ACCEPT; iptables -P FORWARD ACCEPT; iptables -P OUTPUT ACCEPT",
        "iptables -A INPUT -i lo -j ACCEPT",
        "iptables -A INPUT -m conntrack --ctstate ESTABLISHED,RELATED -j ACCEPT",
        "iptables -A FORWARD -m conntrack --ctstate ESTABLISHED,RELATED -j ACCEPT",
        "iptables -A INPUT -p icmp -j ACCEPT",
        "iptables -A FORWARD -p icmp -j ACCEPT",
        "iptables -A INPUT  -p udp --sport 67:68 --dport 67:68 -j ACCEPT",
        "iptables -A FORWARD -p udp --sport 67:68 --dport 67:68 -j ACCEPT",
        "iptables -N SCAN_GUARD 2>/dev/null || true",
        "iptables -F SCAN_GUARD",
        "iptables -A SCAN_GUARD -m recent --name portscan --update --seconds 1 --hitcount 15 -j DROP",
        "iptables -A SCAN_GUARD -m recent --name portscan --set -j RETURN",
        "iptables -A INPUT  -p tcp --syn -j SCAN_GUARD",
        "iptables -A FORWARD -p tcp --syn -j SCAN_GUARD",
        "iptables -A INPUT  -p udp -m recent --name udp_scan --update --seconds 1 --hitcount 60 -j DROP",
        "iptables -A INPUT  -p udp -m recent --name udp_scan --set -j ACCEPT",
        "iptables -A FORWARD -p udp -m recent --name udp_scan --update --seconds 1 --hitcount 60 -j DROP",
        "iptables -A FORWARD -p udp -m recent --name udp_scan --set -j ACCEPT",
    ]
    for c in cmds:
        ts.run(c)

def bring_if_up(ts: TelnetSession, ifname: str):
    ts.run(f"ip link set {ifname} up")
    time.sleep(0.2)

def try_dhcp_on_if(ts: TelnetSession, ifname: str) -> bool:
    rc, _ = ts.run(f"command -v dhclient >/dev/null 2>&1 && dhclient -v -1 {ifname}")
    if rc == 0:
        return True
    rc, _ = ts.run(f"command -v udhcpc >/dev/null 2>&1 && udhcpc -i {ifname} -q -n -t 3")
    if rc == 0:
        return True
    rc, _ = ts.run(f"command -v dhcpcd >/dev/null 2>&1 && dhcpcd -4 -t 10 {ifname}")
    if rc == 0:
        return True
    return False

def set_static_on_if(ts: TelnetSession, ifname: str, cidr: str, gw: str|None):
    ts.run(f"ip addr flush dev {ifname}")
    ts.run(f"ip addr add {cidr} dev {ifname}")
    if gw:
        ts.run(f"ip route replace default via {gw} dev {ifname}")

def discover_ip(ts: TelnetSession, ifname: str) -> tuple[str|None, str|None]:
    _, out1 = ts.run(f"ip -4 addr show dev {ifname}")
    cidr = parse_ipv4_from_ip_addr(out1)
    _, out2 = ts.run("ip route")
    gw = parse_gw_from_ip_route(out2, ifname)
    return cidr, gw

def main():
    ap = argparse.ArgumentParser(description="DHCP orchestrator for GNS3 Linux containers over Telnet")
    ap.add_argument("--config", default="config.generated.json", help="Path to config JSON")
    ap.add_argument("--ip-plan", default="ip_plan.json", help="Path to IP plan JSON for fallbacks + firewall")
    ap.add_argument("--server-ip", default=None, help="Override console_host with this GNS3 server IP (e.g., 192.168.56.101)")
    ap.add_argument("--only", nargs="*", help="Optional list of node names to limit operation")
    ap.add_argument("--if", dest="interfaces", nargs="*", help="Optional interface names to operate (default: from plan or eth0)")
    args = ap.parse_args()

    cfg = json.load(open(args.config, "r", encoding="utf-8"))
    try:
        plan = json.load(open(args.ip_plan, "r", encoding="utf-8"))
    except FileNotFoundError:
        plan = {"interfaces": {}, "node_types": {}}

    address_book_path = "address_book.generated.json"
    try:
        address_book = json.load(open(address_book_path, "r", encoding="utf-8"))
    except FileNotFoundError:
        address_book = {"project_name": cfg.get("project_name",""), "project_id": cfg.get("project_id",""), "nodes": []}
    book_by_name = {n["name"]: n for n in address_book.get("nodes", [])}

    for node in cfg.get("nodes", []):
        name = node.get("name")

        # Skip switches
        nlow = name.lower()
        if "switch" in nlow or "openvswitch" in nlow or nlow.startswith("ovs-"):
            info(f"Skip switch '{name}'")
            continue

        host = (args.server_ip or node.get("console_host") or "127.0.0.1")
        if host == "0.0.0.0":
            host = args.server_ip or "127.0.0.1"
        port = int(node.get("console") or 0)
        if not port:
            warn(f"Node '{name}' lacks a console port; skipping")
            continue

        plan_ifaces = plan.get("interfaces", {}).get(name, [])
        ifnames = [p.get("ifname","eth0") for p in plan_ifaces] or ["eth0"]
        if args.interfaces:
            ifnames = args.interfaces

        ts = TelnetSession(host, port, timeout=10.0)
        try:
            ts.connect()

            # If this is a firewall, set static addresses (from plan) and configure iptables
            if "firewall" in nlow:
                for item in plan_ifaces:
                    ifname = item.get("ifname","eth0")
                    bring_if_up(ts, ifname)
                    if "ip" in item:
                        set_static_on_if(ts, ifname, item["ip"], item.get("gw"))
                configure_firewall(ts)

            # Request DHCP (or fallback) on each target interface
            for ifname in ifnames:
                bring_if_up(ts, ifname)
                got_lease = try_dhcp_on_if(ts, ifname)
                if not got_lease:
                    static = next((i for i in plan_ifaces if i.get("ifname","eth0")==ifname and "ip" in i), None)
                    if static:
                        warn(f"{name}:{ifname} -> DHCP unavailable; using static {static['ip']}")
                        set_static_on_if(ts, ifname, static["ip"], static.get("gw"))
                    else:
                        warn(f"{name}:{ifname} -> DHCP unavailable and no static in plan; leaving unconfigured")

                cidr, gw = discover_ip(ts, ifname)
                info(f"{name}:{ifname} => {cidr} gw={gw}")

                # Update address book
                entry = book_by_name.get(name)
                if not entry:
                    entry = {"name": name, "node_id": node.get("node_id"), "console_host": host, "console_port": port, "interfaces": []}
                    address_book["nodes"].append(entry)
                    book_by_name[name] = entry
                if_list = entry.setdefault("interfaces", [])
                found = False
                for rec in if_list:
                    if rec.get("name")==ifname:
                        rec["ip"] = cidr
                        rec["gw"] = gw
                        found = True
                        break
                if not found:
                    if_list.append({"name": ifname, "ip": cidr, "gw": gw})

        finally:
            ts.close()

    with open(address_book_path, "w", encoding="utf-8") as f:
        json.dump(address_book, f, indent=4)
    info(f"Wrote {address_book_path}")

if __name__ == "__main__":
    main()
