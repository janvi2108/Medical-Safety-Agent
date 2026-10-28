# Architecture

## Overview

The application takes a free-text clinical note and produces:
1. A structured list of medications
2. Verified drug interaction findings (from DDInter 2.0, not the LLM)
3. A deterministic safety status
4. A plain-language patient summary

The design goal throughout is: **the LLM never gets to decide whether a
drug interaction exists or how severe it is.** Only DDInter 2.0's data and
the deterministic rule engine can determine that. The LLM extracts
medications from a messy note. Patient summaries are assembled
deterministically from verified findings and check status.

## Full pipeline

```
Clinical Note (free text)
        │
        ▼
┌─────────────────────┐
│ Agent 1: Extractor    │  ← LLM call. Output: structured Medication list.
└──────────┬───────────┘
           │
           ▼
┌─────────────────────┐
│ Agent 2: Interaction   │  ← NO LLM call. Pure database lookup.
│ Checker                │
└──────────┬───────────┘
           │
           ▼
┌─────────────────────┐
│ Deterministic Safety   │  ← Plain Python if/else. No LLM, no database call.
│ Rule Engine            │
└──────────┬───────────┘
           │
           ▼
┌─────────────────────┐
│ Agent 3: Patient       │  ← Deterministic formatting of verified findings
│ Communicator           │    and check status; no LLM call.
└──────────┬───────────┘
           │
           ▼
   AnalyzeResponse (JSON)
           │
           ▼
      React frontend
```

## What "agent" means here

An agent, in this project, is a component with one clear responsibility
that takes structured input and produces structured output, coordinated by
an orchestrator. Not every agent uses an LLM - Agent 2 explicitly does not,
because its job (looking up a verified fact) doesn't need language
understanding, and using an LLM for it would introduce a chance of
hallucination for no benefit.

**LLM vs agent**: an LLM is a language model - a general-purpose tool for
producing or understanding text. An agent is a role in this application's
pipeline. Agent 1 uses an LLM; Agents 2 and 3 do not. Calling all three
"agents" refers to their position in the pipeline, not to a shared
implementation.

## Why Agent 2 doesn't use LLM reasoning

If you asked an LLM "do warfarin and aspirin interact?", it might get it
right, because that fact is common enough to appear in its training data.
But for less common drug pairs, or drugs from smaller therapeutic classes,
an LLM has no way to distinguish between drug pairs it actually "knows"
about, versus pairs it is inventing a plausible-sounding but wrong answer
for. There is no confidence signal exposed by the LLM
that reliably tells you which case you're in.

DDInter 2.0 doesn't have that problem: a lookup either finds a record or it
doesn't, and the record's content is exactly what's in the dataset.
That's why every interaction fact returned by this API traces back to an
actual database row, and why `services/drug_database.py` has no import of
the LLM client at all - not "chooses not to call it," but has no code path
to call it.

## Orchestration

`backend/agents/orchestrator.py` is the one place that knows the pipeline
order. Each agent function is independent and independently testable
(agents don't call each other directly). The orchestrator calls Agent 1,
resolves the names and checks available pairs with Agent 2, runs the safety
rules on that result, then calls Agent 3 to format findings and any
unmatched medication state.

## Provider-independent LLM layer

```
Agent code
    │  imports
    ▼
services/llm/base.py         (abstract LLMProvider interface)
    │  implemented by
    ▼
services/llm/llm_client.py   (OpenAICompatibleProvider today,
                               AzureOpenAIProvider reserved for later)
```

Agents call `get_llm_client()` and use whatever `LLMProvider` it returns -
they never import a concrete provider class directly. Switching providers
is a one-file change with zero edits to any agent.

## Where Azure (and Vercel) fit

Azure is the **backend cloud infrastructure layer** in this project's
current configuration; the frontend deploys to **Vercel** instead:

- **Vercel** hosts the React frontend (static build, deployed from the
  connected GitHub repo) - see `docs/vercel-deployment.md`
- **Azure App Service** hosts the FastAPI backend (plain Python code, no
  Docker/container step)
- **Azure Database for PostgreSQL** stores the `drugs` / `drug_interactions`
  tables in production
- **Azure Key Vault** holds the LLM API key and database connection string
- **Application Insights** monitors requests, latency, and errors

Azure OpenAI is *not* used, because this project's Azure subscription
currently has no usable GPT model quota (a free-trial billing restriction,
not a technical limitation of Azure OpenAI itself). See
`docs/azure-deployment.md` for the full deployment walkthrough and
`services/llm/llm_client.py` for how a future switch to Azure OpenAI would
be made without touching agent code.

## Why each top-level folder exists

| Folder | Purpose |
|---|---|
| `backend/agents/` | The three pipeline stages plus the orchestrator |
| `backend/api/` | Request/response schemas and route handlers - the HTTP boundary |
| `backend/services/llm/` | Provider-independent LLM abstraction |
| `backend/services/` (rest) | `drug_database.py` (DB-backed interaction lookup) and `safety_rules.py` (deterministic rules) |
| `backend/database/` | Schema definitions and the repository (all raw SQL lives here only) |
| `frontend/` | React + Vite UI |
| `data/raw/ddinter/` | Where official, unmodified DDInter CSVs are placed |
| `data/processed/ddinter/` | Generated SQLite file (local dev only) |
| `data/sample_notes/` | Synthetic notes for manual testing and demos |
| `scripts/` | One-off operational scripts (schema init, data ingestion) - not imported by the app itself |
| `prompts/` | System prompts as plain text, versionable independently of code |
| `tests/` | Deterministic tests - the safety-critical parts (rules, DB lookup) need no mocking at all |
| `docs/` | This documentation set |
