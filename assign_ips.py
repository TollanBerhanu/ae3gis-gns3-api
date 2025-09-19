import argparse
import asyncio
import json
import os
import re
import shutil
import sys
import time

try:
    import telnetlib3 
except ImportError:
    print("Please install telnetlib3: pip install telnetlib3", file=sys.stderr)
    sys.exit(1)

SWITCH_KEYWORDS = ("switch", "openvswitch", "ovs")
def is_switch(name: str) -> bool:
    n = (name or "").lower()
    return any(k in n for k in SWITCH_KEYWORDS)

def is_dhcp_server(name: str) -> bool:
    return "dhcp" in (name or "").lower()

IPV4_RE = re.compile(r"\binet\s+(\d+\.\d+\.\d+\.\d+)/(\d+)")

def extract_first_ipv4(text: str) -> str | None:
    """Return first non-127.x.x.x IPv4 (no prefix), or None."""
    for m in IPV4_RE.finditer(text or ""):
        ip = m.group(1)
        if not ip.startswith("127."):
            return ip
    return None

async def telnet_run(host: str, port: int, command: str, read_secs: float = 5.0) -> str:
    """Run a single command via telnet, read a bit of output, then exit. Return captured text."""
    reader, writer = await telnetlib3.open_connection(host=host, port=port, encoding="utf8")
    try:
        writer.write(command + "\r")
        await writer.drain()

        # Read for a short while (service logs or command chatter)
        deadline = asyncio.get_event_loop().time() + read_secs
        buf = []
        while asyncio.get_event_loop().time() < deadline:
            try:
                chunk = await asyncio.wait_for(reader.read(1024), timeout=0.5)
            except asyncio.TimeoutError:
                chunk = ""
            if chunk:
                buf.append(chunk)

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

async def telnet_run_dhclient_and_show_ip(host: str, port: int, read_secs: float = 15.0) -> str:
    """Run dhclient, then ask for ip -4 addr show; return combined text."""
    reader, writer = await telnetlib3.open_connection(host=host, port=port, encoding="utf8")
    try:
        writer.write("dhclient -v -1\r")
        await writer.drain()

        # Read dhclient chatter
        deadline = asyncio.get_event_loop().time() + read_secs
        buf = []
        while asyncio.get_event_loop().time() < deadline:
            try:
                chunk = await asyncio.wait_for(reader.read(1024), timeout=0.5)
            except asyncio.TimeoutError:
                chunk = ""
            if chunk:
                buf.append(chunk)

        # Show IPv4 addresses
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
        # Exit so GNS3 console stays free
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
    ap = argparse.ArgumentParser(description="Start DHCP servers, then DHCP clients; update config.generated.json with assigned_ip")
    ap.add_argument("--config", default="config.generated.json", help="Path to config JSON")
    ap.add_argument("--host", default=None, help="Override console_host for all nodes (e.g., 192.168.56.101)")
    ap.add_argument("--timeout", type=float, default=15.0, help="Seconds to wait for dhclient output (default 15)")
    ap.add_argument("--dhcp-warmup", type=float, default=2.0, help="Seconds to sleep after starting DHCP servers (default 2)")
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

    # ---------- 1) Start all DHCP servers first ----------
    for n in nodes:
        name = n.get("name", "")
        if not is_dhcp_server(name):
            continue

        host = args.host or n.get("console_host") or "127.0.0.1"
        if host == "0.0.0.0":
            host = args.host or "127.0.0.1"
        port = int(n.get("console") or 0)
        if not port:
            print(f"[WARN] DHCP '{name}': missing console; skipping")
            continue

        print(f"[INFO] DHCP '{name}': starting service -> /usr/local/bin/start.sh")
        try:
            out = asyncio.run(telnet_run(host, port, "/usr/local/bin/start.sh", read_secs=5.0))
            if out.strip():
                print(out, end="")
        except Exception as e:
            print(f"[ERROR] DHCP '{name}': start failed: {e}")

    # Give servers a moment to bind interfaces
    if args.dhcp_warmup > 0:
        print(f"[INFO] Waiting {args.dhcp_warmup:.1f}s for DHCP servers to warm up...")
        time.sleep(args.dhcp_warmup)

    # ---------- 2) Run dhclient on all other nodes ----------
    changed = False
    for n in nodes:
        name = n.get("name", "")
        if is_dhcp_server(name) or is_switch(name):
            print(f"[SKIP] {name}")
            continue

        host = args.host or n.get("console_host") or "127.0.0.1"
        if host == "0.0.0.0":
            host = args.host or "127.0.0.1"
        port = int(n.get("console") or 0)
        if not port:
            print(f"[WARN] {name}: missing 'console' port; skipping")
            continue

        print(f"[INFO] {name}: dhclient via telnet {host}:{port}")
        try:
            text = asyncio.run(telnet_run_dhclient_and_show_ip(host, port, read_secs=args.timeout))
        except Exception as e:
            print(f"[ERROR] {name}: telnet/dhclient failed: {e}")
            n["assigned_ip"] = None
            changed = True
            continue

        ip = extract_first_ipv4(text)
        print(f"[INFO] {name}: assigned_ip = {ip}")
        n["assigned_ip"] = ip
        changed = True

    # ---------- 3) Save updates ----------
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
