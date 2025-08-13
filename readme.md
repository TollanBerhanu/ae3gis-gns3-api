Install dependency:

```bash
pip install requests
```
Example usage (uses your server URL and dummy names—change to match your templates):

```bash
python gns3_topology.py \
  --server http://172.16.194.129:80 \
  --project "My Demo Project" \
  --firewalls 2 \
  --workstations 4 \
  --firewall-template "pfSense Docker" \
  --workstation-template "Ubuntu Workstation" \
  --switch-template "Ethernet switch" \
  --per-row 5
```

If your API requires auth:

```bash
python gns3_topology.py ... --user admin --password secret
```

Notes:
- The script uses `/v2/projects/<project_id>/templates/<template_id>` to instantiate nodes and sets `x,y,name` so they appear neatly spaced in GNS3.

- Each device is linked on its adapter 0/port 0 to switch adapter 0 / port N (incrementing). Adjust the adapter/port if your templates require different interfaces.

- Some switch types auto-start; if `/start` isn’t supported, the script logs a warning and continues.

- Template names must match exactly; you can list them at `http://<GNS3_VM_ip>/v2/templates`.