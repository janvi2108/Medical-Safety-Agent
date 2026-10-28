# Deployment preparation: Vercel + Render

No cloud resources have been created and the application has not been
deployed. Detailed dashboard steps are in [Vercel deployment](docs/vercel-deployment.md)
and [Render deployment](docs/render-deployment.md).

## Runtime versions

- Python 3.12.4, pinned in `.python-version` for Render; `backend/requirements.txt`
  is the backend dependency manifest.
- Node.js 18 or later (Vite 5 requirement; verification environment was
  Node 22.14.0).
- The backend suite was run with Python 3.12.4.

## Local setup

From the repository root, create and activate a virtual environment, then
install the backend dependencies:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r backend/requirements.txt
Copy-Item .env.example .env
```

Set a private Groq key in the repository-root `.env` as `LLM_API_KEY`. Keep
`LLM_PROVIDER=openai_compatible`, `LLM_BASE_URL=https://api.groq.com/openai/v1`,
and the configured `LLM_MODEL` unless deliberately changing the provider.
The frontend receives only `VITE_API_BASE_URL`; never put the provider key
in a `VITE_` variable or frontend environment file.

Initialize the local database and load the original DDInter CSVs, which are
read from `data/raw/ddinter/` by default:

```powershell
python -m scripts.init_db
python -m scripts.load_ddinter
```

Start the backend from the repository root:

```powershell
python -m uvicorn backend.main:app --host 127.0.0.1 --port 8001 --reload
```

In another terminal:

```powershell
Set-Location frontend
npm ci
Copy-Item .env.example .env
npm run dev
```

The local URLs remain `http://127.0.0.1:8001` for the API and
`http://localhost:5173` for the frontend. `GET /health` is a process liveness
check; it does not prove that the LLM or database is ready.

## Vercel frontend settings

- **Root Directory:** `Medication-Safety-Agent/frontend` (or `frontend` if
  `Medication-Safety-Agent` is the repository root)
- **Install:** `npm ci`
- **Build:** `npm run build`
- **Output:** `dist`
- **Environment:** `VITE_API_BASE_URL=https://<your-render-service>.onrender.com`

Set `VITE_API_BASE_URL` for Production and Preview as needed. It is public
frontend configuration and must contain no secret. Production builds have no
localhost fallback.

## Render backend settings

- **Service:** Python 3 Web Service, Free plan
- **Root Directory:** `Medication-Safety-Agent` (or `.` when that is the repo
  root)
- **Build:** `pip install -r backend/requirements.txt && python -m scripts.init_db && python -m scripts.load_ddinter`
- **Start:** `uvicorn backend.main:app --host 0.0.0.0 --port $PORT`
- **Python:** `.python-version` pins `3.12.4`
- **Environment:** `LLM_PROVIDER=openai_compatible`, `LLM_API_KEY=<Groq secret>`,
  `LLM_BASE_URL=https://api.groq.com/openai/v1`,
  `LLM_MODEL=llama-3.3-70b-versatile`, `USE_SQLITE_FALLBACK=true`, and
  `CORS_ORIGINS=https://<your-vercel-project>.vercel.app`.

The CSV-backed SQLite database is built during deploy. Render Free's runtime
filesystem is ephemeral, so do not rely on runtime file changes surviving
restarts or spin-down. For this static interaction catalogue, rebuild from
the original CSVs on every deploy. See the Render guide for the measured
dataset counts and post-deploy verification.

## Verification commands

```powershell
python -m pytest -q --basetemp=.pytest-tmp
python -m compileall -q backend scripts tests
npm --prefix frontend test
npm --prefix frontend run build
```

There is no configured Python linter or type checker. The frontend smoke tests
use Node's built-in test runner and Vite SSR; they are not a substitute for
manual desktop/mobile browser inspection. Check `GET /health` after startup.

## Storage and deployment limits

SQLite is suitable for local development and a single persistent host. Its
file must live on durable storage: many hosted application filesystems are
ephemeral, and multiple instances do not share a local SQLite file. Concurrent
writers can also contend for SQLite locks. Use the supported PostgreSQL path
for horizontally scaled or production workloads.

The API currently has no user authentication or rate limiting. Do not expose
it publicly for sensitive clinical notes without an access-control and abuse
protection plan. No HIPAA, privacy, or medical-device certification is claimed.
Review DDInter's own terms before redistribution or non-educational use.

See [Vercel frontend deployment](docs/vercel-deployment.md) and
[Render backend deployment](docs/render-deployment.md) for the manual steps.
This audit prepared configuration and verification only; deployment and
cloud resource creation have not been performed.
