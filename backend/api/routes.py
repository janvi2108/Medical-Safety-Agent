"""
api/routes.py

FastAPI route definitions. Routes are intentionally thin - they validate
the request, call the orchestrator, and translate exceptions into HTTP
responses. All real logic lives in agents/ and services/.
"""

import logging
import sqlite3
from fastapi import APIRouter, HTTPException
from backend.api.schemas import AnalyzeRequest, AnalyzeResponse
from backend.agents.orchestrator import run_pipeline
from backend.database.repository import DatabaseUnavailableError
from backend.services.llm.llm_client import LLMConfigurationError

logger = logging.getLogger(__name__)
router = APIRouter()

_DATABASE_ERRORS = (sqlite3.DatabaseError,)
try:
    from psycopg2 import Error as PostgresDatabaseError
    _DATABASE_ERRORS += (PostgresDatabaseError,)
except ImportError:
    pass


@router.get("/health")
def health():
    return {"status": "ok"}


@router.post("/analyze", response_model=AnalyzeResponse)
def analyze(request: AnalyzeRequest):
    if not request.clinical_note.strip():
        raise HTTPException(status_code=400, detail="Please enter a clinical note.")

    try:
        return run_pipeline(request.clinical_note)
    except LLMConfigurationError as e:
        logger.error("LLM configuration is incomplete: %s", e)
        raise HTTPException(status_code=503, detail=str(e)) from e
    except DatabaseUnavailableError as e:
        logger.error("Interaction database is not ready: %s", e)
        raise HTTPException(status_code=503, detail=str(e)) from e
    except RuntimeError as e:
        # Raised deliberately for provider or structured extraction failures.
        logger.error("Pipeline stage failed: %s", e)
        raise HTTPException(status_code=502, detail=str(e))
    except FileNotFoundError as e:
        logger.exception("Database not available")
        raise HTTPException(status_code=503, detail="Interaction database is unavailable. Try again shortly.")
    except _DATABASE_ERRORS as e:
        logger.exception("Database check failed")
        raise HTTPException(
            status_code=503,
            detail=("Interaction database is unavailable or uninitialized. Run `python -m scripts.init_db` "
                    "and `python -m scripts.load_ddinter` from the project root. No interaction check was completed."),
        ) from e
    except Exception as e:
        logger.exception("Unexpected pipeline error")
        raise HTTPException(status_code=500, detail="An unexpected error occurred while analyzing this note.")
