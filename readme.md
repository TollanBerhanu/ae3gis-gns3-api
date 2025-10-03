# AE3GIS GNS3 API — Quick Start

## Prerequisites
- Python 3.10+
- The IP and Port of a running GNS3 server

## 1) Configure
Copy the example env file and edit values to match your setup:
```bash
cp .env.example .env
# then open .env and set your GNS3 server URL
````

## 2) Install (create venv + pip install)

**macOS / Linux**

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

**Windows (PowerShell)**

```powershell
python -m venv .venv
.\.venv\Scripts\Activate
pip install -r requirements.txt
```

## 3) Launch the API

```bash
uvicorn api.main:app --reload
```

The server will print the URL (default: `http://127.0.0.1:8000`).

## 4) Read the Docs

* Interactive docs (Swagger): `http://127.0.0.1:8000/docs`
* ReDoc: `http://127.0.0.1:8000/redoc`
* Health check: `GET /health` → `{"status":"ok"}`

> Make sure you configure `.env`, install deps, run the server, then use the docs to interact.


