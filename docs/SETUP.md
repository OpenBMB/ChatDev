Quick setup
============

Overview
--------
This repo has a Python backend (PyProject + uv) and a Vue frontend in ./frontend. Dockerfiles exist for both.

Prereqs
--------
- Python 3.12
- Node 24 / npm
- uv (https://github.com/astral-sh/uv)
- Docker & Docker Compose (optional)

Local (recommended using uv)
---------------------------
1. Install uv: pip install uv
2. Sync deps: uv sync
3. Run backend (example): python server_main.py --port 6400 --host 0.0.0.0
4. Frontend:
   cd frontend
   npm install
   npm run dev

Alternative using requirements.txt
----------------------------------
1. python -m venv .venv
2. On Windows: .\.venv\Scripts\Activate   (Linux/macOS: source .venv/bin/activate)
3. pip install -r requirements.txt
4. Run backend: python server_main.py --port 6400 --host 0.0.0.0

Docker
------
Bring up both services (backend + frontend):

  docker compose up --build

This uses root Dockerfile and frontend/Dockerfile. Ports: backend 6400, frontend 5173.

CI
--
A GitHub Actions workflow (.github/workflows/ci.yml) was added to run backend tests and build the frontend on push/pull requests to main.

Notes
-----
- The repo uses Python 3.12 and "uv" for deterministic installs. If you prefer pip, the requirements.txt is present.
- If anything custom is needed (DB, secrets), provide details and a follow-up will add env/config.
