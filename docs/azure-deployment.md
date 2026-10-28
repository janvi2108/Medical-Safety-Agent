# Azure Deployment (Backend)

## Target architecture

```
Internet
   │
   ├── React (frontend/)
   │      ↓
   │  Vercel  ← see docs/vercel-deployment.md
   │
   └── FastAPI (backend/)
          ↓
      Azure App Service
          │
          ├── LLM Provider API (Groq, or OpenAI - not an Azure resource)
          ├── Azure Database for PostgreSQL
          ├── Azure Key Vault
          └── Application Insights
```

This document covers the backend half only (Azure). The frontend deploys
to Vercel instead of Azure Static Web Apps - see `docs/vercel-deployment.md`
for that half.

Azure OpenAI is intentionally **not** part of this architecture right now
- see `docs/architecture.md` ("Where Azure fits") for why, and
`backend/services/llm/llm_client.py` for how a future switch would work.

No Docker is used anywhere in this deployment - the backend deploys as
plain Python code directly to App Service (Step 4 below).

## 1. Resource Group

```bash
az group create --name medication-safety-rg --location eastus
```

## 2. Azure Database for PostgreSQL (Flexible Server, Burstable tier)

```bash
az postgres flexible-server create \
  --resource-group medication-safety-rg \
  --name medsafety-db \
  --tier Burstable --sku-name Standard_B1ms \
  --storage-size 32 --version 16
```

Set `DATABASE_URL` (in `.env` locally, or App Service settings in
production) to the connection string this command outputs, and set
`USE_SQLITE_FALLBACK=false`. Then initialize the schema and load data:

```bash
python -m scripts.init_db
python -m scripts.load_ddinter
```

## 3. Azure Key Vault

```bash
az keyvault create --name medsafety-kv --resource-group medication-safety-rg

az keyvault secret set --vault-name medsafety-kv --name llm-api-key --value "<your-llm-api-key>"
az keyvault secret set --vault-name medsafety-kv --name database-connection-string --value "<your-postgres-url>"
```

`backend/config.py`'s `resolve_secret()` reads from Key Vault when
`USE_KEY_VAULT=true`, using the App Service's Managed Identity - no key or
password is ever typed into App Service's configuration blade directly.

## 4. App Service (backend - no Docker required)

This project deploys as plain Python code, not a container:

```bash
az appservice plan create --name medsafety-plan --resource-group medication-safety-rg --is-linux --sku B1

az webapp create --resource-group medication-safety-rg --plan medsafety-plan \
  --name medication-safety-agent-api --runtime "PYTHON:3.11"

az webapp config set --resource-group medication-safety-rg --name medication-safety-agent-api \
  --startup-file "uvicorn backend.main:app --host 0.0.0.0 --port 8000"
```

Enable Managed Identity and grant it Key Vault access:
```bash
az webapp identity assign --resource-group medication-safety-rg --name medication-safety-agent-api

az keyvault set-policy --name medsafety-kv \
  --object-id <principal-id-from-previous-command> \
  --secret-permissions get list
```

Set app settings:
```bash
az webapp config appsettings set --resource-group medication-safety-rg --name medication-safety-agent-api \
  --settings USE_KEY_VAULT=true AZURE_KEY_VAULT_URL=https://medsafety-kv.vault.azure.net/ USE_SQLITE_FALLBACK=false CORS_ORIGINS=https://your-app.vercel.app
```

Deploy the code:
```bash
az webapp up --resource-group medication-safety-rg --name medication-safety-agent-api
```

## 5. Frontend deployment

The frontend does **not** deploy to Azure in this setup - see
`docs/vercel-deployment.md` for the full Vercel deployment steps.

## 6. Application Insights

```bash
az monitor app-insights component create \
  --app medsafety-insights --location eastus --resource-group medication-safety-rg
```

Copy the connection string into the App Service's app settings as
`APPLICATIONINSIGHTS_CONNECTION_STRING` - `backend/main.py` detects it
automatically at startup and begins sending request traces. No further
code changes are needed. Do not log clinical note text or secrets - see
"Monitoring" in the root README for the logging discipline this project
follows.

## 7. CORS

`CORS_ORIGINS` in `backend/config.py` controls which frontend origins can
call the API. Once your frontend is deployed on Vercel (see
`docs/vercel-deployment.md`), set this to that Vercel URL:

```bash
az webapp config appsettings set --resource-group medication-safety-rg --name medication-safety-agent-api \
  --settings CORS_ORIGINS=https://your-app.vercel.app
```

The default (`http://localhost:5173`) is for local development only.

## Deployment flow summary

```
git push
   │
   ├── frontend/**  changes → Vercel rebuilds and deploys automatically (connected repo)
   │
   └── backend/**   changes → az webapp up (or your own CI) redeploys App Service
```

