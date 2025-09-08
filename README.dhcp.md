
# DHCP Orchestrator (Windows-friendly)

This script telnets into your **Linux container nodes** and requests DHCP leases (with fallback to static
from your `ip_plan.json`). It also configures the **firewall** (iptables) to allow pings and DHCP,
and to throttle/drop Nmap-style port scans. Works on **Windows, Linux, macOS** — no Bash/Expect required.

## Files
- `orchestrate_dhcp.py` – the orchestrator (pure Python, uses `telnetlib`).
- `address_book.generated.json` – automatically maintained; lists assigned IPs per node/interface.

## Requirements
- Python 3.10+ on your host.
- GNS3 node consoles reachable from your machine (Telnet). If `console_host` is `0.0.0.0` in your config,
  override with `--server-ip`, e.g., `--server-ip 192.168.56.101`.

## DHCP behavior
- Tries, in order: `dhclient`, `udhcpc`, `dhcpcd`.
- If none is present or leases fail, falls back to your `ip_plan.json` static entries (per-node, per-ifname).
- Updates `address_book.generated.json` with discovered IP/GW.

## Firewall
- Detected by node name containing "firewall". It applies iptables rules:
  - allow ICMP and established/related
  - allow DHCP (UDP 67/68) on INPUT/FORWARD
  - "scan guard" using `-m recent` for TCP SYN bursts and mild UDP limiter
- Uses static IPs for firewall **from `ip_plan.json`** (so set firewall addresses there).

## Example usage (Windows PowerShell or CMD)
```powershell
python orchestrate_dhcp.py --config config.generated.json --ip-plan ip_plan.json --server-ip 192.168.56.101

# Limit to specific nodes or interfaces:
python orchestrate_dhcp.py --only Workstation-1 Workstation-2 --server-ip 192.168.56.101
python orchestrate_dhcp.py --if eth0 --server-ip 192.168.56.101
```
