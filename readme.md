# AE3GIS GNS3 API

## Prereqs

* Python 3.10+
* `pip install -r reqirements.txt`

---

## 1) Build the scenario (create topology + export config)

1. Edit `topology_config/scenario.json` (or start from `scenario_template.json`).
2. Run the builder:

   ```bash
   python build_scenario.py --scenario topology_config/scenario.json --server http://<GNS3_SERVER_IP>:80 --start --config-out config.generated.json
   ```

   This creates/starts nodes and writes `config.generated.json`.

---

## 2) Start DHCP servers, then DHCP clients (updates config in place)

```bash
python assign_ips.py --config config.generated.json --host <GNS3_SERVER_IP>
```

What it does:

* Finds nodes with “dhcp” in the name, runs `/usr/local/bin/start.sh`.
* Waits a moment, then runs `dhclient -v -1` on other nodes to assign IPs (skips names containing `switch/openvswitch/ovs`).
* Parses the first IPv4 and writes `"assigned_ip"` back into `config.generated.json`.

**Options**

* `--config` : path to the config file (default `config.generated.json`)
* `--host`   : override `console_host` for all nodes (helpful when it’s `0.0.0.0`)
* `--timeout`: seconds to watch dhclient output per node (default `15`)
* `--dhcp-warmup`: seconds to wait after bringing up DHCP servers before clients start (default `2`)

## Output

* **In-place update** of `config.generated.json`:

  ```json
  {
    "name": "Workstation-1",
    "console_host": "0.0.0.0",
    "console": 5001,
    "assigned_ip": "192.168.0.23"
  }
  ```
* Backup file: `config.generated.backup.json`.

## Tips

* The script **expects** a shell and **`dhclient`** in your Linux containers.
  If `dhclient` isn’t installed in a node, that node may remain without `assigned_ip`.
* **Firewalls and switches**: currently, firewalls are treated as regular nodes unless their name matches the switch/DHCP patterns. If you want a different behavior, rename or ping me to tweak filters.
* If Telnet consoles are bound to `127.0.0.1` inside the GNS3 VM, use `--host <GNS3 VM IP>` so your Windows host can reach them.