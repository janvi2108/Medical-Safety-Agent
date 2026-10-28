# Medication Safety Agent Chain

A full-stack application that analyzes a clinical note, extracts
medications, checks them against **DDInter 2.0** for known drug-drug
interactions, and presents a plain-language patient summary — built
around one non-negotiable principle: **the LLM never decides whether a
drug interaction exists.**

> Educational prototype — not medical advice. Do not start, stop, or
> change medication based on this application. Consult a qualified
> healthcare professional.

## Problem statement

LLMs are good at language tasks and unreliable at recalling specific,
high-stakes facts with any guaranteed accuracy. For something like a drug
interaction, a confidently wrong LLM answer is a real safety risk. This
project separates the two concerns explicitly: an LLM reads messy clinical
text, while deterministic code presents results and a real database
(DDInter 2.0) plus rule logic are the only things that ever
determine whether an interaction exists or how severe it is.

## Features

- Extracts medications (name, dose, frequency, route) from free-text
  clinical notes using an LLM
- Checks every unique medication pair against DDInter 2.0 via a
  normalized PostgreSQL/SQLite database - **not** LLM inference
- Deterministic safety rule engine decides warning levels from verified
  data only
- Deterministic plain-language patient summary built only from verified
  findings and unmatched/no-record state
- Clearly distinguishes "no interaction found" from "verified safe" -
  and clearly flags medications that couldn't be matched to the database
  at all
- React + Vite frontend with a calm, clinical, non-generic design
- Full test suite covering extraction, interaction lookup, safety rules,
  and the API layer
- Provider-independent LLM layer (currently configured for Groq; ready
  for Azure OpenAI later with no agent code changes)

## Architecture

See `docs/architecture.md` for the full breakdown. Summary:

```
Clinical Note
      │
      ▼
Agent 1: Extractor (LLM)
      │
      ▼
Agent 2: Interaction Checker (DDInter 2.0 lookup - no LLM)
      │
      ▼
Deterministic Safety Rules
      │
      ▼
Agent 3: Patient Communicator (deterministic, database findings only)
      │
      ▼
React UI
```

## Tech stack

| Layer | Choice |
|---|---|
| Frontend | React + Vite (JavaScript) |
| Backend | Python + FastAPI |
| Database | PostgreSQL (production) / SQLite (local dev) |
| LLM | Provider-independent (Groq by default) |
| Dataset | DDInter 2.0 |
| Frontend hosting | Vercel |
| Backend hosting | Azure App Service |
| Secrets | Azure Key Vault |
| Monitoring | Application Insights |

No Docker is used anywhere in this project's setup or deployment.

## Agent architecture

Three logical agents, one deterministic rule engine, one orchestrator.
See `docs/interview-preparation.md` for detailed Q&A on each, and
`docs/architecture.md` for the full pipeline diagram.

## DDInter dataset

See `docs/ddinter.md` for the complete explanation of ingestion, schema
detection, and the `source_risk` vs `normalized_risk` distinction. The
original DDInter CSV files are stored under `data/raw/ddinter/` - see
`data/raw/ddinter/README.md` and `docs/ddinter.md` for provenance and schema.

## Data pipeline

```
data/raw/ddinter/ (official CSVs, untouched)
        │
        ▼
scripts/load_ddinter.py  (schema detection, normalization, validation)
        │
        ▼
drugs + drug_interactions tables (SQLite locally / PostgreSQL in production)
        │
        ▼
services/drug_database.py (name resolution, canonical pair lookup)
        │
        ▼
Agent 2 (interaction_checker.py)
```

## Database

See `docs/database.md` for the full schema, indexes, and canonical pair
ordering explanation.

## API

```
GET  /health
POST /analyze
```

Request:
```json
{ "clinical_note": "Patient is taking warfarin 5 mg once daily and aspirin 81 mg daily." }
```

Response (shape):
```json
{
  "medications": [],
  "interactions": { "pairs_checked": 0, "interactions_found": [], "unmatched_drugs": [], "highest_normalized_risk": null },
  "safety": { "safety_level": "none", "show_critical_banner": false, "banner_message": null },
  "patient_summary": null,
  "warnings": []
}
```

## Frontend

React + Vite, plain JavaScript (chosen for simplicity over TypeScript at
this project's current stage - see `docs/interview-preparation.md` if
asked why). Component structure in `frontend/src/components/`: `Header`,
`ClinicalNoteInput`, `MedicationTable`, `InteractionCard`, `RiskBadge`,
`PatientSummary`, `LoadingState`, `ErrorMessage`, `Disclaimer`.

## Safety architecture

The single most important design decision in this project:

- Agent 2 (`interaction_checker.py`) has **no import** of the LLM client
  anywhere in its call path - it is structurally impossible for an
  interaction fact to come from anywhere but the database.
- `services/safety_rules.py` is pure Python logic with no LLM or database
  dependency - fully covered by exhaustive unit tests, not a statistical
  evaluation.
- Agent 3 uses no LLM; it formats verified findings and check status
  deterministically, so generated text cannot add or suppress results.
- "No interaction found" and "verified safe" are never conflated, anywhere
  in the code or the UI.

## Installation

### Prerequisites
- Python 3.11+
- Node.js 18+
- (Optional, production-style setup) PostgreSQL - SQLite is used by
  default for local development, no setup required

### Windows

```powershell
git clone <your-repo-url>
cd Medication-Safety-Agent

python -m venv venv
venv\Scripts\activate
pip install -r backend/requirements.txt

copy .env.example .env
REM edit .env and set LLM_API_KEY (see "Configuration" below)
```

### macOS / Linux

```bash
git clone <your-repo-url>
cd Medication-Safety-Agent

python -m venv venv
source venv/bin/activate
pip install -r backend/requirements.txt

cp .env.example .env
# edit .env and set LLM_API_KEY
```

## Configuration

Copy `.env.example` to `.env` in the repository root and set `LLM_API_KEY`
to a valid Groq API key. The application loads that file relative to the
project, so backend startup works from any current directory. Existing
process environment variables take precedence. Do not commit `.env`.

```
LLM_API_KEY=your_groq_api_key_here
```

Get a free key at https://console.groq.com/keys. Leave
`USE_SQLITE_FALLBACK=true` for local development - no PostgreSQL setup
required.

## Running locally

```bash
# from the project root, with venv activated
uvicorn backend.main:app --reload --port 8001
```

API docs available at `http://127.0.0.1:8001/docs`.

In a second terminal:
```bash
cd frontend
npm ci
cp .env.example .env
npm run dev
```

Frontend at `http://localhost:5173`.

## Loading DDInter

```bash
python -m scripts.init_db        # creates the schema
python -m scripts.load_ddinter   # reads data/raw/ddinter/ddinter_downloads_code_*.csv
```

The loader reads only the supplied DDInter category CSV files. If they are
missing, it fails with an explicit error; it never substitutes synthetic
records. Set `RAW_DDINTER_DIR` only if the files are stored elsewhere.
Re-running ingestion is safe and skips already imported pairs. The source
files contain interaction IDs, names, and source level only; they do not
include descriptions, management, or alternatives.

Start the React frontend in a second terminal from `frontend/` with
`npm run dev`. The backend starts with `uvicorn backend.main:app --reload --port 8001`
from the project root. If the database is missing or empty, initialize it
with the commands above; the API reports an actionable 503 until then.
Set `LLM_API_KEY` in `.env` for medication
extraction; interaction checks and patient summaries are deterministic.

## Testing

```bash
pip install -r backend/requirements.txt   # includes pytest
pytest tests/ -v
npm --prefix frontend test
npm --prefix frontend run build
```

Covers extraction schema validation, drug matching/normalization,
interaction lookup (known pairs, reversed pairs, unknowns, duplicates),
deterministic safety rules (exhaustive, no mocking needed), and the API
layer (valid/invalid/empty requests, failure handling).

## Evaluation

See `docs/evaluation.md` for the full methodology - building a synthetic
evaluation set, metrics to compute per pipeline stage, and how to
interpret and report results honestly.

## Render deployment (backend)

See `docs/render-deployment.md` for the Render Web Service setup, including
the build-time DDInter SQLite initialization and Free filesystem limits.

## Vercel deployment (frontend)

See `docs/vercel-deployment.md` for the frontend root directory, Vite build
settings, and `VITE_API_BASE_URL` configuration. Both provider guides are
summarized in `DEPLOYMENT.md`.

## Limitations

- Drug name matching is normalization + a small alias table, not a
  clinical-grade resolution system - unmatched drugs are reported
  explicitly rather than guessed at.
- DDInter coverage, correctness, and update frequency are not independently
  assessed by this application (see `docs/ddinter.md`).
- Evaluation numbers (if you run the process in `docs/evaluation.md`) are
  based on a small, self-authored synthetic note set - not a clinical
  validation study.
- This is a portfolio/educational project, not a certified medical
  device.

## Future improvements

- Fuzzy/RxNorm-based drug name matching instead of exact-normalization + alias table
- Per-stage latency logging surfaced in the UI
- A pre-built evaluation harness (currently documented as a recommended
  approach in `docs/evaluation.md`, not shipped as a script)
- Azure OpenAI as a second LLM provider once quota is available (the
  abstraction in `backend/services/llm/` is already built for this)

## Disclaimer

Educational prototype — not medical advice. Do not start, stop, or
change medication based on this application. Consult a qualified
healthcare professional.

## Dataset attribution

Drug interaction data is sourced from **DDInter 2.0**
(https://ddinter2.scbdd.com), a separate work from this project's source
code. DDInter's dataset is governed by its own terms - see `LICENSE` for
how this project's code license and DDInter's dataset terms are kept
distinct, and check https://ddinter2.scbdd.com directly before using this
data beyond personal/educational development.
