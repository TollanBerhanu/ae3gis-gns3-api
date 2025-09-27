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

---

## 3) Run the FastAPI service

The CLI tools above are now available via a REST API powered by FastAPI.

### Create and activate a virtual environment (Windows PowerShell)

```powershell
python -m venv .venv
.\.venv\Scripts\activate
pip install -r requirements.txt
```

### Start the API with Uvicorn

```powershell
uvicorn api.main:app --reload
```

* `--reload` restarts the server when you edit code (handy during development).
* By default the service listens on `http://127.0.0.1:8000`.

### Built-in docs

Open `http://127.0.0.1:8000/docs` for Swagger UI or `http://127.0.0.1:8000/redoc` for ReDoc.

---

## 4) Interacting with the API

Below are example `curl` calls. You can also use Postman, HTTPie, or the Swagger UI “Try it out” buttons.

### Health check

```powershell
curl http://127.0.0.1:8000/health
```

Expect `{"status":"ok"}` when the service is up.

### Build a scenario

```powershell
curl -X POST http://127.0.0.1:8000/scenario/build `
  -H "Content-Type: application/json" `
  -d @topology_config/scenario.json
```

Notes:

* The payload reuses the same JSON you feed into `build_scenario.py`.
* To override the GNS3 API endpoint or authentication, extend the body:

  ```json
  {
    "scenario": { ... },
    "base_url": "http://172.16.194.129:80",
    "username": "admin",
    "password": "supersecret",
    "start_nodes": true,
    "config_path": "config.generated.json"
  }
  ```

* The response includes the project id/name, nodes/links created, and where the config file was written.

### Run DHCP assignment

```powershell
curl -X POST http://127.0.0.1:8000/dhcp/assign `
  -H "Content-Type: application/json" `
  -d '{"host_override":"172.16.194.129","dhcp_warmup":2,"dhclient_timeout":15}'
```

Response fields mirror the CLI output: results for each DHCP server/client run, whether the config was updated, and the path of any backup file.

### Upload a script to multiple nodes

Prepare a JSON file, e.g. `payloads/iptables.json`:

```json
{
  "host_override": "172.16.194.129",
  "concurrency": 3,
  "scripts": [
    {
      "node_name": "IPTables-Firewall",
      "local_path": "scripts/firewall/hardening.sh",
      "remote_path": "/opt/hardening.sh",
      "run_after_upload": true,
      "overwrite": true,
      "run_timeout": 20,
      "shell": "bash"
    }
  ]
}
```

Then call:

```powershell
curl -X POST http://127.0.0.1:8000/scripts/push `
  -H "Content-Type: application/json" `
  -d @payloads/iptables.json
```

Each item reports upload status (including base64 decode or chmod errors) and optional execution output.

### Run an existing script

```powershell
curl -X POST http://127.0.0.1:8000/scripts/run `
  -H "Content-Type: application/json" `
  -d '{"host_override":"172.16.194.129","runs":[{"node_name":"Workstation-1","remote_path":"/opt/hardening.sh","shell":"bash","timeout":15}]}'
```

The response includes exit codes, stdout, and stderr for each node’s execution attempt.

---

## Troubleshooting

* **401/403 from GNS3** – double-check credentials or API token. If Basic auth is required, pass `username` and `password` in the scenario build payload.
* **Telnet timeouts** – confirm the consoles are reachable from the machine running the API (use `host_override` if the config contains `0.0.0.0`).
* **Script path errors** – the API validates that `local_path` resides under the configured scripts directory (defaults to `scripts/`). Update `GNS3_API_SCRIPTS_DIR` if you store scripts elsewhere.