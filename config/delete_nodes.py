import requests
from dotenv import load_dotenv

load_dotenv() 

gns3_server_ip = os.getenv("GNS3_SERVER_IP") or '192.168.56.101'
gns3_server_port = os.getenv("GNS3_SERVER_PORT") or '80'
BASE = f"http://{gns3_server_ip}:{gns3_server_port}/v2"
PROJECT_NAME = "ae3gis-scenario-builder-test"   # change me
# project_id = '8b26f4d4-5445-4e86-86a0-d46944d8e85b' #project.project_id
AUTH = None                  # e.g., ('admin','password') if auth enabled

# 1) Resolve project_id
projects = requests.get(f"{BASE}/projects", auth=AUTH).json()
proj = next((p for p in projects if p["name"] == PROJECT_NAME), None)
if not proj:
    raise SystemExit(f"Project '{PROJECT_NAME}' not found")
project_id = proj["project_id"]
print(f"Project: {PROJECT_NAME} ({project_id})")

# 2) Stop nodes (optional but polite)
requests.post(f"{BASE}/projects/{project_id}/nodes/stop", auth=AUTH)

# 3) Delete nodes
nodes = requests.get(f"{BASE}/projects/{project_id}/nodes", auth=AUTH).json()
for n in nodes:
    nid = n["node_id"]
    print(f"Deleting node {nid} ({n.get('name')})")
    requests.delete(f"{BASE}/projects/{project_id}/nodes/{nid}", auth=AUTH)

# 4) Delete links (optional clean)
links = requests.get(f"{BASE}/projects/{project_id}/links", auth=AUTH).json()
for l in links:
    lid = l["link_id"]
    print(f"Deleting link {lid}")
    requests.delete(f"{BASE}/projects/{project_id}/links/{lid}", auth=AUTH)

print("Done.")
