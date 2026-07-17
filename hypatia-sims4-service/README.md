# 🦉 Hypatia Sims4ModGuard — Backend API Service

AI-powered Sims 4 mod conflict analysis service built with FastAPI and Claude.  
Free for the community forever — built by **Hucifer & 🦉 Hypatia**.

> GitHub: https://github.com/HuciferX/Sims4ModGuard

---

## What It Does

| Endpoint | Description |
|---|---|
| `POST /analyze-log` | Send your `lastException.txt` — Hypatia (Claude AI) diagnoses which mods are broken and gives step-by-step fixes |
| `POST /check-mod` | Look up a single `.package` filename against the known conflicts database |
| `GET /conflicts` | Get the full curated conflicts database |
| `POST /submit-conflict` | Community-submit a new conflict as a GitHub Issue |
| `GET /health` | Health check — returns status, version, and DB size |

Interactive API docs available at `http://localhost:8765/docs` when running locally.

---

## Quick Start (Local)

### 1. Requirements
- Python 3.11+
- An [Anthropic API key](https://console.anthropic.com/) (for AI analysis)
- Optional: a GitHub Personal Access Token (for `/submit-conflict`)

### 2. Install & run

```bash
cd hypatia-sims4-service
pip install -r requirements.txt
cp .env.example .env
# Edit .env and add your ANTHROPIC_API_KEY
uvicorn main:app --host 0.0.0.0 --port 8765 --reload
```

The API will be live at `http://localhost:8765`.

### 3. Test it

```bash
# Health check
curl http://localhost:8765/health

# Analyze a log
curl -X POST http://localhost:8765/analyze-log \
  -H "Content-Type: application/json" \
  -d '{"content": "...paste lastException.txt here...", "patch_version": "1.121"}'

# Check a mod file
curl -X POST http://localhost:8765/check-mod \
  -H "Content-Type: application/json" \
  -d '{"filename": "mc_cmd_center.ts4script"}'
```

---

## Docker Deployment

### Build & run

```bash
docker build -t hypatia-sims4-service .
docker run -d \
  --name hypatia-api \
  -p 8765:8765 \
  --env-file .env \
  --restart unless-stopped \
  hypatia-sims4-service
```

### With docker-compose

```yaml
version: "3.9"
services:
  hypatia-api:
    build: .
    ports:
      - "8765:8765"
    env_file:
      - .env
    restart: unless-stopped
```

---

## Deploying to a VPS / Cloud

This service is designed to run behind a reverse proxy (nginx / Caddy) with TLS.

### Example nginx config (domain: `api.hySims.app`)

```nginx
server {
    listen 443 ssl;
    server_name api.hySims.app;

    location / {
        proxy_pass http://127.0.0.1:8765;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_read_timeout 60s;
    }
}
```

Run with: `docker run -p 127.0.0.1:8765:8765 --env-file .env hypatia-sims4-service`

---

## How the Windows App Connects

The Windows GUI app (`sims4modguard/`) uses `api_client.py` to communicate with this service.

```python
from sims4modguard.api_client import analyze_log, check_mod, is_available

# Check if the backend is reachable
if is_available():
    result = analyze_log(log_content, server="https://api.hySims.app")
    print(result["summary"])
    for step in result["fix_steps"]:
        print(f"  • {step}")
```

The client defaults to `https://api.hySims.app` but accepts any server URL,  
allowing players to self-host the backend and point the GUI at their own instance.

### Offline / no-key mode

If `ANTHROPIC_API_KEY` is not set, the service automatically falls back to  
heuristic pattern-matching analysis — no AI required, still useful.

---

## Environment Variables

| Variable | Required | Description |
|---|---|---|
| `ANTHROPIC_API_KEY` | For AI analysis | Claude API key from console.anthropic.com |
| `GITHUB_TOKEN` | For `/submit-conflict` | Fine-grained PAT with Issues: Read & Write |
| `PORT` | No | Service port (default: 8765) |
| `LOG_LEVEL` | No | DEBUG / INFO / WARNING / ERROR (default: INFO) |

Copy `.env.example` → `.env` and fill in your values.

---

## AI Model

This service uses **Claude Haiku** (`claude-haiku-4-5`) — chosen for:
- Sub-second response times on typical log files
- Low cost (suitable for a free community tool)
- Prompt caching on the Hypatia system prompt to cut token costs on repeated requests

The system prompt instructs Claude to act as 🦉 Hypatia — a Sims 4 mod expert  
who gives precise, actionable mod-specific diagnostics.

---

## Architecture

```
Windows App (customtkinter GUI)
        │
        │  HTTP/JSON  (api_client.py)
        ▼
🦉 Hypatia FastAPI Service (port 8765)
        │
        ├── /analyze-log  ──►  Claude Haiku (Anthropic API)
        ├── /check-mod    ──►  In-memory conflict DB
        ├── /conflicts    ──►  In-memory conflict DB
        ├── /submit-conflict ► GitHub Issues API
        └── /health
```

---

## Contributing

Found a broken mod? Use `/submit-conflict` or open an issue at  
https://github.com/HuciferX/Sims4ModGuard/issues

PRs welcome — especially new entries for `conflict_db.py`!

---

*Built with ❤️ by Hucifer & 🦉 Hypatia — free for the Sims 4 community forever.*
