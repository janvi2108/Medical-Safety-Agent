# Render Deployment (FastAPI backend)

This guide configures the existing FastAPI application as a Render Free Web
Service. It does not create cloud resources. Keep Groq credentials in Render's
backend environment settings only; never add them to a `VITE_` variable.

## Service settings

Create a **Web Service**, select the Python 3 runtime and Free plan, and connect
the repository containing `Medication-Safety-Agent/`. Set the **Root
Directory** to `Medication-Safety-Agent` (the repository root if this folder is
the repo itself). This root is required because the app imports `backend.*`,
loads `prompts/`, and reads `data/raw/ddinter/` relative to the project root.

Use these commands:

```text
Build Command: pip install -r backend/requirements.txt && python -m scripts.init_db && python -m scripts.load_ddinter
Start Command: uvicorn backend.main:app --host 0.0.0.0 --port $PORT
```

The `.python-version` file pins Python to the version used for local
verification. `backend/requirements.txt` is the dependency manifest. The
loader initializes the schema and imports the supplied original CSVs; build
must fail if the CSV files are missing or invalid.

## Environment variables

Set these in the Render service's **Environment** settings:

| Variable | Value |
|---|---|
| `LLM_PROVIDER` | `openai_compatible` |
| `LLM_API_KEY` | `<your Groq API key>` (secret) |
| `LLM_BASE_URL` | `https://api.groq.com/openai/v1` |
| `LLM_MODEL` | `llama-3.3-70b-versatile` (or a model enabled for your account) |
| `USE_SQLITE_FALLBACK` | `true` |
| `CORS_ORIGINS` | `https://<your-vercel-project>.vercel.app` |

Add additional exact Vercel preview origins as comma-separated values if
needed. Do not use `*`. `PORT` is assigned by Render; do not hard-code a port
in the Start Command. Do not set `DATABASE_URL` for this SQLite deployment.

## SQLite behavior on Free

The repository includes eight original DDInter CSVs (about 13 MB total). A
local read-only inspection of the existing `data/processed/ddinter/ddinter.db`
found 1,939 drugs and 160,235 DDInter interactions; the database is about
17.2 MB. The database is ignored by `.gitignore`, so it is not a reliable
deployment input. The CSVs are present and are not excluded by the current
`.gitignore` rules. This local directory has no Git metadata, so tracked/remote
status cannot be confirmed here. Before connecting a Git provider, ensure all
eight `data/raw/ddinter/ddinter_downloads_code_*.csv` files are committed to
the branch Render will build.

The Render build command recreates the database from those CSVs in the
deployment filesystem. A local isolated run read all 222,383 rows across the
eight files, imported 160,235 interactions, rejected none, and completed in
about 8 seconds. At request time, the application queries the loaded SQLite
database; analysis does not ingest or update DDInter records.

Render Free has an ephemeral filesystem: files written while the service is
running can disappear after a restart, spin-down, or redeploy. This app's
DDInter catalogue is static, so rebuilding it during each deploy avoids
relying on a runtime-created database surviving. Rebuild/redeploy when the
source dataset or loader changes. Do not add runtime uploads or mutable data
to this SQLite file. For mutable or multi-instance production storage, use a
persistent database; Free Render Postgres itself has a limited lifetime and
is not a permanent storage solution.

The app currently opens SQLite with its normal local read/write connection,
but the analysis path only performs reads. Schema creation and ingestion are
build-time tasks in this configuration. A failed/empty import causes the API
to report that interaction data is unavailable rather than presenting a
successful interaction check.

## Verify after deployment

1. Confirm the Render deploy log shows successful installation, schema setup,
   and DDInter ingestion. Expect 160,235 imported DDInter interactions for the
   supplied files.
2. Request `https://<render-service>.onrender.com/health`; expect HTTP 200 and
   `{"status":"ok"}`. This endpoint is liveness only.
3. Submit a synthetic test note through the deployed Vercel UI. Confirm the
   browser Network panel sends `POST https://<render-service>.onrender.com/analyze`
   and receives the expected response contract.
4. If the browser reports a CORS error, set `CORS_ORIGINS` to the exact
   `https://<vercel-project>.vercel.app` origin (scheme and host, no path),
   save, and redeploy/restart the Render service.
5. Test a known DDInter interaction with a synthetic note and verify the
   source classification is shown. Do not use real patient information for
   deployment checks.

## Public service limits

The API has no authentication or rate limiting. Do not expose it to sensitive
clinical notes until access control and abuse protection are implemented and
reviewed. This project is not clinically validated or certified as a medical
device. Render Free services may spin down when idle, so the first request
after inactivity can take about a minute.
