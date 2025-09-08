#!/usr/bin/env python3
# Simple DHCP kicker for one GNS3 node via telnet (Windows-friendly, Python 3.13+)
# Usage examples:
#   python simple_dhcp.py --node "Workstation-1" --config config.generated.json --host 192.168.56.101
#   python simple_dhcp.py --node "Workstation-2" --if eth0 --config config.generated.json --host 192.168.56.101
#
# Notes:
# - Requires: pip install telnetlib3
# - If the node's console_host in config is "0.0.0.0", pass --host <GNS3 server IP>.

import argparse
import asyncio
import json
import sys
import telnetlib3

async def run_dhcp(host: str, port: int, iface: str | None):
    reader, writer = await telnetlib3.open_connection(host=host, port=port, encoding="utf8")
    try:
        # Build the command: dhclient -v -1 [iface]
        cmd = f"dhclient -v -1 {iface}" if iface else "dhclient -v -1"
        # Send the command
        writer.write(cmd + "\r")
        await writer.drain()

        # Read and echo output for a short while
        # (dhclient prints useful logs; you can increase the timeout if needed)
        deadline = asyncio.get_event_loop().time() + 15.0
        buf = []
        while asyncio.get_event_loop().time() < deadline:
            try:
                chunk = await asyncio.wait_for(reader.read(1024), timeout=0.5)
            except asyncio.TimeoutError:
                chunk = ""
            if not chunk:
                # no more output at the moment
                continue
            buf.append(chunk)
            # Print as it arrives so you can see progress live
            print(chunk, end="", flush=True)

        # Optionally show the final IPv4 addresses
        writer.write("ip -4 addr show\r")
        await writer.drain()
        await asyncio.sleep(1.0)
        try:
            more = await asyncio.wait_for(reader.read(4096), timeout=1.0)
        except asyncio.TimeoutError:
            more = ""
        if more:
            print(more, end="", flush=True)

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

def main():
    ap = argparse.ArgumentParser(description="Run dhclient on a single GNS3 node via telnet")
    ap.add_argument("--node", required=True, help="Exact node name from config.generated.json")
    ap.add_argument("--config", default="config.generated.json", help="Path to config JSON")
    ap.add_argument("--host", default=None, help="Override console_host (e.g., your GNS3 server IP)")
    ap.add_argument("--if", dest="iface", default=None, help="Optional interface name (e.g., eth0)")
    args = ap.parse_args()

    with open(args.config, "r", encoding="utf-8") as f:
        cfg = json.load(f)

    node = next((n for n in cfg.get("nodes", []) if n.get("name") == args.node), None)
    if not node:
        print(f"[ERROR] Node '{args.node}' not found in {args.config}", file=sys.stderr)
        sys.exit(1)

    host = args.host or node.get("console_host") or "127.0.0.1"
    if host == "0.0.0.0":
        if not args.host:
            print("[WARN] console_host is 0.0.0.0 — pass --host <GNS3 server IP>", file=sys.stderr)
        # still use 0.0.0.0 if user didn't override; many setups map it fine from local
    port = int(node.get("console") or 0)
    if not port:
        print(f"[ERROR] Node '{args.node}' has no 'console' port in {args.config}", file=sys.stderr)
        sys.exit(1)

    print(f"[INFO] Connecting to {args.node} at {host}:{port} ...")
    asyncio.run(run_dhcp(host, port, args.iface))

if __name__ == "__main__":
    main()
