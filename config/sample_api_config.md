Build the Scenairo:
- URL: `http://127.0.0.1:8000/scenario/build`
- Method: `POST`
- Payload:
```
{
  "base_url": "http://192.168.56.101",
  "start_nodes": true,
  
  "scenario": {
    "gns3_server_ip": "192.168.56.101",
    "project_name": "ae3gis-scenario-builder-test",
    "project_id": "2b54d41e-c6fa-4f41-8c60-531eef7fd69d",

    "templates": {
      "test-client": "749baf44-97ea-40a7-8eb3-3793f13a775a",
      "nginx-server": "c40b3744-575c-446e-9d26-e28b7f0a8c9b"
    },

    "nodes": [
      { "name": "Client-401", "template_id": "749baf44-97ea-40a7-8eb3-3793f13a775a", "x": -300, "y": -250 },
      { "name": "Client-402", "template_id": "749baf44-97ea-40a7-8eb3-3793f13a775a", "x": -250, "y": -250 },
      { "name": "Client-403", "template_id": "749baf44-97ea-40a7-8eb3-3793f13a775a", "x": -200, "y": -250 },
      { "name": "Client-404", "template_id": "749baf44-97ea-40a7-8eb3-3793f13a775a", "x": -150, "y": -250 },
      { "name": "Client-405", "template_id": "749baf44-97ea-40a7-8eb3-3793f13a775a", "x": -100, "y": -250 },
      { "name": "Client-406", "template_id": "749baf44-97ea-40a7-8eb3-3793f13a775a", "x": -50, "y": -250 },
      { "name": "Client-407", "template_id": "749baf44-97ea-40a7-8eb3-3793f13a775a", "x": 0, "y": -250 },
      { "name": "Client-408", "template_id": "749baf44-97ea-40a7-8eb3-3793f13a775a", "x": 50, "y": -250 },
      { "name": "Client-409", "template_id": "749baf44-97ea-40a7-8eb3-3793f13a775a", "x": 100, "y": -250 },
      { "name": "Client-410", "template_id": "749baf44-97ea-40a7-8eb3-3793f13a775a", "x": 150, "y": -250 },
      { "name": "Client-411", "template_id": "749baf44-97ea-40a7-8eb3-3793f13a775a", "x": 200, "y": -250 },
      { "name": "Client-412", "template_id": "749baf44-97ea-40a7-8eb3-3793f13a775a", "x": 250, "y": -250 },
      { "name": "Client-413", "template_id": "749baf44-97ea-40a7-8eb3-3793f13a775a", "x": 300, "y": -250 },
			{
				"name": "OpenvSwitch-41",
				"template_id": "1cd31b8f-8afc-40f7-b9f3-92c4d124b695",
				"x": 0,
				"y": -140
			},
			{
				"name": "DHCP-41",
				"template_id": "11daf0e0-afa9-4d36-94cd-04ff92b3d7ae",
				"x": 0,
				"y": 0
			},
			{
				"name": "Server-41",
				"template_id": "c40b3744-575c-446e-9d26-e28b7f0a8c9b",
				"x": 300,
				"y": -250
			}
    ],

    "links": [
      { "nodes": [ { "node_id": "Client-401", "adapter_number": 0, "port_number": 0 }, { "node_id": "OpenvSwitch-41", "adapter_number": 1, "port_number": 0 } ] },
      { "nodes": [ { "node_id": "Client-402", "adapter_number": 0, "port_number": 0 }, { "node_id": "OpenvSwitch-41", "adapter_number": 2, "port_number": 0 } ] },
      { "nodes": [ { "node_id": "Client-403", "adapter_number": 0, "port_number": 0 }, { "node_id": "OpenvSwitch-41", "adapter_number": 3, "port_number": 0 } ] },
      { "nodes": [ { "node_id": "Client-404", "adapter_number": 0, "port_number": 0 }, { "node_id": "OpenvSwitch-41", "adapter_number": 4, "port_number": 0 } ] },
      { "nodes": [ { "node_id": "Client-405", "adapter_number": 0, "port_number": 0 }, { "node_id": "OpenvSwitch-41", "adapter_number": 5, "port_number": 0 } ] },
      { "nodes": [ { "node_id": "Client-406", "adapter_number": 0, "port_number": 0 }, { "node_id": "OpenvSwitch-41", "adapter_number": 6, "port_number": 0 } ] },
      { "nodes": [ { "node_id": "Client-407", "adapter_number": 0, "port_number": 0 }, { "node_id": "OpenvSwitch-41", "adapter_number": 7, "port_number": 0 } ] },
      { "nodes": [ { "node_id": "Client-408", "adapter_number": 0, "port_number": 0 }, { "node_id": "OpenvSwitch-41", "adapter_number": 8, "port_number": 0 } ] },
      { "nodes": [ { "node_id": "Client-409", "adapter_number": 0, "port_number": 0 }, { "node_id": "OpenvSwitch-41", "adapter_number": 9, "port_number": 0 } ] },
      { "nodes": [ { "node_id": "Client-410", "adapter_number": 0, "port_number": 0 }, { "node_id": "OpenvSwitch-41", "adapter_number": 10, "port_number": 0 } ] },
      { "nodes": [ { "node_id": "Client-411", "adapter_number": 0, "port_number": 0 }, { "node_id": "OpenvSwitch-41", "adapter_number": 11, "port_number": 0 } ] },
      { "nodes": [ { "node_id": "Client-412", "adapter_number": 0, "port_number": 0 }, { "node_id": "OpenvSwitch-41", "adapter_number": 12, "port_number": 0 } ] },
      { "nodes": [ { "node_id": "Client-413", "adapter_number": 0, "port_number": 0 }, { "node_id": "OpenvSwitch-41", "adapter_number": 13, "port_number": 0 } ] },
      { "nodes": [ { "node_id": "Server-41", "adapter_number": 0, "port_number": 0 }, { "node_id": "OpenvSwitch-41", "adapter_number": 14, "port_number": 0 } ] },
      { "nodes": [ { "node_id": "DHCP-41", "adapter_number": 0, "port_number": 0 }, { "node_id": "OpenvSwitch-41", "adapter_number": 15, "port_number": 0 } ] }
    ]
  }
}
```

---

- URL: `http://127.0.0.1:8000/scripts/push`
- Method: `POST`
- Payload: 
**To assign IP and start the web server:**
```
{
  "scripts": [
    {
      "node_name": "Server-41",
      "local_path": "./run_server.sh",
      "remote_path": "/run_server.sh",
      "run_after_upload": true,
      "executable": true,
      "overwrite": true,
      "run_timeout": 10,
      "shell": "sh"
    }
  ],
	"host_override": "http://192.168.56.101",
  "concurrency": 5
}
```

**To start the DHCP server:**
```
{
  "scripts": [
    {
      "node_name": "DHCP-41",
      "local_path": "./run_dhcp.sh",
      "remote_path": "/usr/run_dhcp.sh",
      "run_after_upload": true,
      "executable": true,
      "overwrite": true,
      "run_timeout": 10,
      "shell": "sh"
    }
  ],
	"host_override": "http://192.168.56.101",
  "concurrency": 5
}
```

**To request IP from DHCP and start benign traffic from client:**
```
{
  "scripts": [
		
    {
      "node_name": "Client-401",
      "local_path": "./run_http.sh",
      "remote_path": "/usr/run_http.sh",
      "run_after_upload": true,
      "executable": true,
      "overwrite": true,
      "run_timeout": 10,
      "shell": "sh"
    },
    {
      "node_name": "Client-402",
      "local_path": "./run_http.sh",
      "remote_path": "/usr/run_http.sh",
      "run_after_upload": true,
      "executable": true,
      "overwrite": true,
      "run_timeout": 10,
      "shell": "sh"
    },
    {
      "node_name": "Client-403",
      "local_path": "./run_http.sh",
      "remote_path": "/usr/run_http.sh",
      "run_after_upload": true,
      "executable": true,
      "overwrite": true,
      "run_timeout": 10,
      "shell": "sh"
    },
    {
      "node_name": "Client-404",
      "local_path": "./run_http.sh",
      "remote_path": "/usr/run_http.sh",
      "run_after_upload": true,
      "executable": true,
      "overwrite": true,
      "run_timeout": 10,
      "shell": "sh"
    },
    {
      "node_name": "Client-405",
      "local_path": "./run_http.sh",
      "remote_path": "/usr/run_http.sh",
      "run_after_upload": true,
      "executable": true,
      "overwrite": true,
      "run_timeout": 10,
      "shell": "sh"
    },
    {
      "node_name": "Client-406",
      "local_path": "./run_http.sh",
      "remote_path": "/usr/run_http.sh",
      "run_after_upload": true,
      "executable": true,
      "overwrite": true,
      "run_timeout": 10,
      "shell": "sh"
    },
    {
      "node_name": "Client-407",
      "local_path": "./run_http.sh",
      "remote_path": "/usr/run_http.sh",
      "run_after_upload": true,
      "executable": true,
      "overwrite": true,
      "run_timeout": 10,
      "shell": "sh"
    },
    {
      "node_name": "Client-408",
      "local_path": "./run_http.sh",
      "remote_path": "/usr/run_http.sh",
      "run_after_upload": true,
      "executable": true,
      "overwrite": true,
      "run_timeout": 10,
      "shell": "sh"
    },
    {
      "node_name": "Client-409",
      "local_path": "./run_http.sh",
      "remote_path": "/usr/run_http.sh",
      "run_after_upload": true,
      "executable": true,
      "overwrite": true,
      "run_timeout": 10,
      "shell": "sh"
    },
    {
      "node_name": "Client-410",
      "local_path": "./run_http.sh",
      "remote_path": "/usr/run_http.sh",
      "run_after_upload": true,
      "executable": true,
      "overwrite": true,
      "run_timeout": 10,
      "shell": "sh"
    },
    {
      "node_name": "Client-411",
      "local_path": "./run_http.sh",
      "remote_path": "/usr/run_http.sh",
      "run_after_upload": true,
      "executable": true,
      "overwrite": true,
      "run_timeout": 10,
      "shell": "sh"
    },
    {
      "node_name": "Client-412",
      "local_path": "./run_http.sh",
      "remote_path": "/usr/run_http.sh",
      "run_after_upload": true,
      "executable": true,
      "overwrite": true,
      "run_timeout": 10,
      "shell": "sh"
    },
    {
      "node_name": "Client-413",
      "local_path": "./run_http.sh",
      "remote_path": "/usr/run_http.sh",
      "run_after_upload": true,
      "executable": true,
      "overwrite": true,
      "run_timeout": 10,
      "shell": "sh"
    }
  ],
	"host_override": "http://192.168.56.101",
  "concurrency": 5
}
```