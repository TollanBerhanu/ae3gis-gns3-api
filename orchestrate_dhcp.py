#!/usr/bin/env python3
# Simple bulk DHCP for GNS3 nodes via telnet (Windows-friendly, Python 3.13+)
# - Reads config.generated.json
# - Skips nodes whose NAME contains: switch, openvswitch, ovs, dhcp
# - Telnets to each remaining node, runs `dhclient -v -1`
# - Parses first non-loopback IPv4 and writes it back to the SAME config file as "assigned_ip"
#
# Usage:
#   python simple_bulk_dhcp.py --config config.generated.json --host 192.168.56.101
#   # --host overrides console_host when it's 0.0.0.0 or missing

import argparse
import asyncio
import json
import os
import re
import shutil
import sys
import time

try:
    import telnetlib3  # pip install telnetlib3
except ImportError:
    print("Please install telnetlib3: pip install telnetlib3", file=sys.stderr)
    sys.exit(1)

SKIP_KEYWORDS = ("switch", "openvswitch", "ovs", "dhcp")

def should_skip(name: str) -> bool:
    n = (name or "").lower()
    return any(k in n for k in SKIP_KEYWORDS)

async def telnet_run_dhclient(host: str, port: int, read_secs: float = 15.0) -> str:
    """Connect, run dhclient, then ip -4 addr show; return combined output text."""
    reader, writer = await telnetlib3.open_connection(host=host, port=port, encoding="utf8")
    try:
        # Kick DHCP
        writer.write("dhclient -v -1\r")
        await writer.drain()

        # Read dhclient chatter for a bit
        deadline = asyncio.get_event_loop().time() + read_secs
        buf = []
        while asyncio.get_event_loop().time() < deadline:
            try:
                chunk = await asyncio.wait_for(reader.read(1024), timeout=0.5)
            except asyncio.TimeoutError:
                chunk = ""
            if chunk:
                buf.append(chunk)

        # Ask for IPv4 addresses
        writer.write("ip -4 addr show\r")
        await writer.drain()
        await asyncio.sleep(1.0)
        try:
            more = await asyncio.wait_for(reader.read(4096), timeout=1.0)
        except asyncio.TimeoutError:
            more = ""
        if more:
            buf.append(more)

        return "".join(buf)
    finally:
        try:
            writer.write("exit\r")
            await writer.drain()
        except Exception:
            pass
        try:
            writer.close()
            if hasattr(writer, "wait_closed"):
                await writer.wait_closed()
        except Exception:
            pass

IPV4_RE = re.compile(r"\binet\s+(\d+\.\d+\.\d+\.\d+)/(\d+)")

def extract_first_ipv4(text: str) -> str | None:
    """Return first non-127.x.x.x IPv4 (no prefix), or None."""
    for m in IPV4_RE.finditer(text or ""):
        ip = m.group(1)
        if not ip.startswith("127."):
            return ip
    return None

def main():
    ap = argparse.ArgumentParser(description="Bulk DHCP on non-switch/non-dhcp nodes; updates config.generated.json in place")
    ap.add_argument("--config", default="config.generated.json", help="Path to config JSON")
    ap.add_argument("--host", default=None, help="Override console_host for all nodes (e.g., 192.168.56.101)")
    ap.add_argument("--timeout", type=float, default=15.0, help="Seconds to wait for dhclient output (default 15)")
    args = ap.parse_args()

    # Load config
    try:
        with open(args.config, "r", encoding="utf-8") as f:
            cfg = json.load(f)
    except FileNotFoundError:
        print(f"[ERROR] {args.config} not found", file=sys.stderr)
        sys.exit(1)

    nodes = cfg.get("nodes", [])
    if not isinstance(nodes, list):
        print("[ERROR] 'nodes' array missing/invalid in config", file=sys.stderr)
        sys.exit(1)

    # Backup once
    backup_path = args.config.replace(".json", ".backup.json")
    try:
        shutil.copyfile(args.config, backup_path)
        print(f"[INFO] Backed up config to {backup_path}")
    except Exception as e:
        print(f"[WARN] Could not create backup: {e}")

    # Process nodes sequentially
    changed = False
    for n in nodes:
        name = n.get("name", "")
        if should_skip(name):
            print(f"[SKIP] {name}")
            continue

        host = args.host or n.get("console_host") or "127.0.0.1"
        if host == "0.0.0.0":  # typical from GNS3; user should override with --host
            host = args.host or "127.0.0.1"

        port = int(n.get("console") or 0)
        if not port:
            print(f"[WARN] {name}: missing 'console' port; skipping")
            continue

        print(f"[INFO] {name}: telnet {host}:{port} -> dhclient")
        try:
            text = asyncio.run(telnet_run_dhclient(host, port, read_secs=args.timeout))
        except Exception as e:
            print(f"[ERROR] {name}: telnet/dhclient failed: {e}")
            continue

        ip = extract_first_ipv4(text)
        print(f"[INFO] {name}: assigned_ip = {ip}")
        # Write back (even if None, to show we attempted)
        n["assigned_ip"] = ip
        changed = True

    # Save only if something changed
    if changed:
        try:
            with open(args.config, "w", encoding="utf-8") as f:
                json.dump(cfg, f, indent=4)
            print(f"[DONE] Updated {args.config}")
        except Exception as e:
            print(f"[ERROR] Failed to write {args.config}: {e}")
            sys.exit(1)
    else:
        print("[INFO] No changes to write.")

if __name__ == "__main__":
    main()
