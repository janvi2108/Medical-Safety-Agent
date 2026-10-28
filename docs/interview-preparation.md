# Interview Preparation

Plain-language answers you can actually use. Read these, then try
explaining each one in your own words out loud - that's the real test of
whether you understand it, not whether you can recite this file.

---

## Basic concepts

**What is FastAPI?**
A Python framework for building APIs. You write normal Python functions,
add a decorator like `@router.post("/analyze")`, and FastAPI handles
turning HTTP requests into Python objects and back, using Pydantic models
to validate the data automatically.

**What is React?**
A JavaScript library for building user interfaces out of reusable
components. Instead of writing one big HTML page, you write small pieces
(`Header`, `MedicationTable`, `InteractionCard`) that each manage their own
piece of the page and can be reused or tested independently.

**What is PostgreSQL?**
An open-source relational database. "Relational" means data is organized
into tables with defined relationships between them (in this project,
`drug_interactions` rows reference `drugs` rows by ID) - as opposed to a
single flat file or an unstructured document store.

**What is an API?**
A defined way for two pieces of software to talk to each other. In this
project, the React frontend and the FastAPI backend are separate
programs; the API (`POST /analyze`) is the contract between them - "send
me a clinical note as JSON, I'll send back extracted medications and
interaction findings as JSON."

**What is REST?**
A style of API design built around HTTP methods (GET to read, POST to
create/submit) and URLs that represent resources. `POST /analyze` follows
this style: it's an HTTP POST, to a URL describing the action being
requested.

**What is JSON?**
A text format for structured data - objects with key-value pairs, arrays,
strings, numbers. It's what the frontend and backend exchange; a
`Medication` object becomes `{"name": "warfarin", "dose": "5 mg", ...}`.

**What is Pydantic?**
A Python library for defining the *shape* of your data (a `Medication` has
a `name`, an optional `dose`, etc.) and having it validated automatically.
If the LLM returns malformed data, or a request is missing a field,
Pydantic raises a clear error instead of letting bad data silently flow
through the system.

---

## Project-specific questions

**Why did you use an LLM at all?**
Two tasks in this pipeline genuinely need language understanding: reading
a messy, free-text clinical note and pulling out medication names (Agent
1), and turning a structured, verified finding into a plain-language
explanation a patient can understand (Agent 3). Both are language tasks
an LLM is well-suited for.

**Why didn't you use an LLM to check interactions?**
Because that's not a language task - it's a factual lookup, and LLMs can
produce a confident-sounding wrong answer with no signal to tell you
it's wrong. For a safety-critical fact like a drug interaction, I wanted
a system where "did these two drugs interact" always traces back to an
actual record in a real database, not a model's internal (and
unverifiable) belief.

**Why DDInter?**
It's a real, structured, publicly accessible drug interaction database,
which is exactly what a lookup-based Agent 2 needs. See `docs/ddinter.md`
for the full reasoning and its limitations.

**How does Agent 1 work?**
It sends the clinical note plus a system prompt (in `prompts/extractor.txt`)
to the LLM, asking for a JSON list of medications with name/dose/frequency/
route. The JSON is validated against the `Medication` Pydantic model before
it's used anywhere else - if the LLM returns something malformed, that's
caught immediately rather than silently propagating.

**How does Agent 2 work?**
It takes the medication list from Agent 1, generates every unique pair,
normalizes each drug name (lowercase, alias resolution), looks each drug
up in the `drugs` table, and if both drugs in a pair are found, queries
`drug_interactions` for that exact canonical pair. No LLM call happens
anywhere in this path.

**How does Agent 3 work?**
It deterministically formats the *already-verified* interaction findings
and the *already-decided* safety level into patient-friendly text. It makes
no LLM call, so it cannot add or suppress an interaction claim.

**What is orchestration?**
Coordinating multiple independent components in a defined order.
`agents/orchestrator.py` is the orchestrator here - it calls Agent 1, then
Agent 2, then the safety rules, then Agent 3, and assembles their outputs
into one final response. The agents themselves don't know about each
other or call each other directly.

**How are medication pairs generated?**
Using `itertools.combinations()` on the list of unique medication names -
for N medications, this produces every 2-element subset without
repeating a pair or including a medication paired with itself.

**Why n(n-1)/2?**
That's the number of ways to choose 2 items from a set of N without
regard to order - equivalently, "everyone shakes hands with everyone else
exactly once." For 3 medications, that's 3 pairs; for 4, it's 6.

**How are drug names normalized?**
Lowercased and whitespace-collapsed (`normalize_name()` in
`services/drug_database.py`), then checked against a small alias table
(e.g. "Tylenol" → "acetaminophen") for common brand names. This is
deliberately simple, not a full clinical drug-matching system - see
"Limitations" in `docs/ddinter.md`.

**How does the database lookup work?**
Both drug names are resolved to database IDs, the two IDs are sorted
(`sorted([id_a, id_b])`) to get canonical ordering, and a single query
looks up the `drug_interactions` row for that exact `(drug_a_id,
drug_b_id)` pair. See `docs/database.md` for why sorting the IDs avoids
needing to check both possible orderings.

**What happens if a drug isn't found?**
It's reported as `unmatched` in the API response rather than silently
skipped. The safety rule engine then returns `safety_level: "unverified"`
- explicitly different from "no interaction found" - because an
unverified check should never be presented as a clean result.

---

## Architecture questions

**Why FastAPI?**
Built-in request/response validation via Pydantic, automatic interactive
API docs (`/docs`), and it's async-capable if the project ever needs to
handle concurrent LLM calls efficiently.

**Why React?**
Component-based structure fits this project naturally - `MedicationTable`,
`InteractionCard`, and `PatientSummary` are each independent, reusable
pieces reflecting the three pipeline stages.

**Why PostgreSQL?**
It's a mature, relational database well-suited to data with real
relationships (drugs, and interactions *between* drugs) - and it has a
managed, low-maintenance option on Azure (Azure Database for PostgreSQL)
for production.

**Why separate agents?**
Each has one job and can be tested, understood, and reasoned about
independently. If Agent 2 has a bug, you know to look at
`interaction_checker.py` and `drug_database.py` - not the whole pipeline.

**Why a separate repository layer?**
`database/repository.py` is the only file that knows whether it's talking
to SQLite or PostgreSQL. Everything above it (`services/drug_database.py`
and up) is unaware of that distinction, so the underlying database can
change without touching business logic.

**Why deterministic safety rules?**
Because whether a critical warning is shown shouldn't depend on how the
LLM happened to phrase something that day. It's a fixed rule anyone can
read and audit, tested exhaustively in `tests/test_safety_rules.py`
without needing an API key.

**Why a provider-independent LLM architecture?**
Because this project was built while Azure OpenAI quota was unavailable,
and I didn't want the whole system's architecture to depend on a billing
decision outside my control. The abstraction (`services/llm/base.py` +
`llm_client.py`) means the LLM provider can change without touching any
agent code.

---

## Azure questions

**Why Azure?**
It's a mainstream cloud platform with managed services covering every
layer this project needs (compute, database, secrets, monitoring), and
learning it has direct relevance to enterprise/internship environments.

**Why App Service?**
A managed way to host a web application (the FastAPI backend) without
manually provisioning and patching a server - it handles the runtime,
scaling, and HTTPS certificate for you.

**Why Vercel for the frontend instead of Azure Static Web Apps?**
Vercel is purpose-built for exactly this kind of static Vite/React build -
connect a GitHub repo, and every push rebuilds and redeploys automatically,
with zero-config preview URLs per pull request. The backend still runs on
Azure (App Service, PostgreSQL, Key Vault, Application Insights) because
those are the pieces this project specifically wanted hands-on Azure
experience with; the frontend's hosting choice is independent of that.

**Why PostgreSQL (on Azure)?**
Same reasoning as the general PostgreSQL choice, but managed - Azure
handles backups, patching, and availability instead of running your own
database server.

**What is Key Vault?**
A managed secret store. Instead of typing an API key into App Service's
configuration (visible to anyone with portal access, and easy to
accidentally commit if config is exported), the app authenticates to Key
Vault using its own identity (Managed Identity) and fetches secrets at
runtime - no secret is ever typed in twice or stored in two places.

**What is Application Insights?**
A monitoring service that captures request traces, response times, and
errors automatically once you give the app its connection string - useful
for answering "why did this request take 4 seconds" or "how often is this
endpoint failing" without adding your own logging infrastructure.

**How does deployment work?**
See `docs/azure-deployment.md` for the full step-by-step - in short:
push code, App Service picks up backend changes (via `az webapp up` or a
CI pipeline), Static Web Apps rebuilds the frontend automatically from a
connected GitHub repo.
