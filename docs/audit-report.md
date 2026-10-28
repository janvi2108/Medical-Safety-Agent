# Project audit and DDInter integration report

Audit date: 2026-10-26

## Root cause of demo data usage

`backend/config.py` defaulted `RAW_DDINTER_DIR` to `data/raw/ddinter/`
(before the fix, around line 39). The eight original files were at the
project root, so `scripts/load_ddinter.py` did not discover them. Its
former `_discover_csv_files` function explicitly chose
`data/raw/ddinter/synthetic_demo_data.csv` if no category CSV was found.
The loader printed a warning, but the app could still return demo
interactions. There was no frontend hardcoded interaction result.

The loader reads only `ddinter_downloads_code_*.csv` from
`data/raw/ddinter/` by default, and missing files produce a clear error.
The repository interaction query filters for rows whose source is
`DDInter 2.0`.

## Supplied source files inspected

All eight files opened as UTF-8 CSV with the same five columns:
`DDInterID_A`, `Drug_A`, `DDInterID_B`, `Drug_B`, `Level`. IDs and levels
are strings; IDs follow the `DDInter` plus numeric suffix format. Required
fields were present in every row. There were no malformed IDs, blank
required fields, or exact duplicate rows within a file. No mechanism,
description, management, or alternative fields are present.

| File | Bytes | Rows |
|---|---:|---:|
| `ddinter_downloads_code_A.csv` | 3,343,434 | 56,367 |
| `ddinter_downloads_code_B.csv` | 867,726 | 15,140 |
| `ddinter_downloads_code_D.csv` | 1,520,704 | 25,681 |
| `ddinter_downloads_code_H.csv` | 705,088 | 11,727 |
| `ddinter_downloads_code_L.csv` | 3,885,702 | 65,389 |
| `ddinter_downloads_code_P.csv` | 317,460 | 5,492 |
| `ddinter_downloads_code_R.csv` | 1,793,766 | 30,563 |
| `ddinter_downloads_code_V.csv` | 700,777 | 12,024 |
| **Total** | **13,134,657** | **222,383** |

Representative row: `DDInter1263` / `Naltrexone`, `DDInter1` /
`Abacavir`, level `Moderate`. Observed `Level` counts were Major 33,896,
Moderate 130,367, Minor 10,938, and Unknown 47,182. A/B columns provide
two IDs but no direction field; the application treats each pair as
unordered and supports reverse-order lookup. The CSVs do not explain
direction semantics, so that interpretation remains an explicit
application assumption.

There are 160,235 unique unordered source-ID pairs. The other 62,148 rows
repeat a pair across category files; all repeated pairs had the same
`Level`. This resulted in zero rejected rows and 62,148 skipped duplicate
rows. The distinct drug IDs/names map one-to-one in this supplied export.

## Ingestion and database verification

The command `python -m scripts.load_ddinter` completed against the
configured local SQLite path `data/processed/ddinter/ddinter.db`.

- Files processed: 8
- Rows read: 222,383
- Distinct interactions imported: 160,235
- Rejected rows: 0
- Duplicate rows skipped: 62,148
- Database drugs: 1,939
- Database DDInter interaction rows: 160,235

No database existed at the configured path during initial inspection, so
this operation created a new local database; no existing database was
reset or overwritten. Verification compared the loader counts to the
database source-filtered count, looked up the representative interaction
and both stored source identifiers in SQLite, and queried that interaction
through the checker in reverse medication order. It returned one record
with source `DDInter 2.0` and source level `Moderate`. An isolated test
also reran ingestion and verified that it inserted zero new rows.

An independent full-set comparison joined every imported interaction back
to both DDInter source identifiers and compared the unordered ID pair and
source level against all eight CSVs: 160,235 source pairs and 160,235
database pairs, with zero missing pairs, zero extra pairs, and zero level
mismatches.

## Confirmed bugs fixed

- Root data files were missed and silently replaced by the demo CSV. The
  loader now points to `data/raw/ddinter/`, and there is no fallback.
- Loader schema assumptions did not match the actual data, and its prior
  pair deduplication used drug database IDs. The loader now validates the
  actual header, preserves source IDs and levels, counts rejects and
  duplicates, rejects conflicting levels, and imports transactionally.
- A single unmatched medication bypassed database resolution. Every
  extracted medication is now resolved, even when no pair can be formed.
- The patient communicator could phrase unmatched or empty results as “no
  interaction found” and could add or suppress claims through LLM output.
  It now produces deterministic text directly from verified records and
  check state.
- An unclassified source level was previously reduced to a caution status.
  It is now marked unverified.
- Malformed extractor JSON was returned as a generic server error. It is
  now reported as a pipeline/provider failure.
- Empty pair lookups no longer appear to prove safety in the UI or patient
  summary.
- SQLite and PostgreSQL query errors return HTTP 503 with an explicit
  incomplete-check message instead of an empty interaction response.
- The repository-root `.env` is loaded by absolute project path, independent
  of backend working directory, with process environment variables taking
  precedence. Missing/invalid LLM setup and empty/uninitialized databases
  now produce actionable API errors without returning raw model output.

## Files changed

- `backend/config.py`
- `backend/database/repository.py`
- `backend/agents/interaction_checker.py`
- `backend/agents/orchestrator.py`
- `backend/agents/patient_communicator.py`
- `backend/agents/extractor.py`
- `backend/services/safety_rules.py`
- `backend/api/schemas.py`
- `backend/api/routes.py`
- `scripts/load_ddinter.py`
- `scripts/init_db.py` (usage comment)
- `frontend/src/components/InteractionCard.jsx`
- `tests/test_ddinter_ingestion.py`
- `tests/test_interactions.py`
- `tests/test_patient_communicator.py`
- `tests/test_safety_rules.py`
- `tests/test_extractor.py`
- `tests/test_api.py`
- `docs/audit-report.md`
- `README.md`
- `.gitignore`
- `docs/ddinter.md`
- `docs/database.md`
- `data/raw/ddinter/README.md`

## Verification results

- Baseline backend suite: `python -m pytest -q --basetemp=.pytest-tmp` —
  **22 passed**. The default pytest temp location was permission-denied in
  this Windows environment; using an in-project basetemp worked.
- Post-change backend suite: `python -m pytest -q --basetemp=.pytest-tmp` —
  **34 passed** (includes parsing and importing all supplied files into a
  temporary SQLite database and repeat-ingestion assertions).
- `python -m compileall -q backend scripts tests` — passed.
- Frontend: `npm.cmd run build` — Vite production build passed, 42 modules
  transformed. Dependencies were installed locally to enable this build.
- API tests exercise `GET /health` and `POST /analyze` request/response
  handling with the pipeline mocked, including a database failure response.
  A live LLM-backed `/analyze` call was
  not run because this audit had no usable provider credentials.

## Attribution, restrictions, and limitations

DDInter's terms page states the data is under CC BY-NC-SA 4.0 and limits
downloaded content to personal, non-commercial, informational, or scholarly
use absent additional service terms. The page also warns that DDInter does
not guarantee accuracy or completeness and that absence of a record does
not mean there is no interaction. Consult the [official DDInter terms]
(https://ddinter2.scbdd.com/terms/) before redistribution or other use.
The supplied category files are listed on the [official download page]
(https://ddinter2.scbdd.com/download/).

The application still depends on LLM extraction, which may omit or
misidentify medication names; unmatched names are surfaced, but a plausible
incorrect extraction cannot be authoritatively corrected without a
medication identity service. DDInter coverage and clinical accuracy are
not independently validated here. No live PostgreSQL connection was
available for testing. The npm install command reported one moderate and
one high dependency advisory; no automatic dependency upgrades were made.
No automated frontend test suite is configured; the production build was
verified instead. The old `prompts/patient_communicator.txt` is now unused.
The repository `.env` file was empty during the 2026-10-26 follow-up audit,
and no process `LLM_API_KEY` was configured, so no live Groq request was
made; the existing `.env` was left untouched.

## Commands

On 2026-10-26, the eight unchanged source CSVs were moved from the project
root into `data/raw/ddinter/`. Their combined size is 13,134,657 bytes and
they contain 222,383 rows (160,235 unique pairs). The existing database
was preserved. The obsolete `synthetic_demo_data.csv` was removed; a test
still creates an isolated synthetic fixture under a temporary directory
to verify that no fallback occurs.

From the project root, in the configured Python environment:

```bash
python -m scripts.init_db
python -m scripts.load_ddinter
uvicorn backend.main:app --reload --port 8001
```

In a second terminal:

```bash
cd frontend
npm install
npm run dev
```

Build the frontend with `npm run build` from `frontend/`. Set `LLM_API_KEY`
in the repository-root `.env` for medication extraction. Set
`RAW_DDINTER_DIR` only if the original category files are stored elsewhere.
