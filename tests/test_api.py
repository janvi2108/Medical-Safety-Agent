"""
tests/test_api.py

Tests the /health and /analyze endpoints using FastAPI's TestClient.
The orchestrator is mocked here so these tests don't require a real LLM
API key or a populated database - they test the API layer's request
validation and error handling, not the pipeline logic itself (that's
covered by test_extractor.py, test_interactions.py, test_safety_rules.py).
"""

import sys
import os
import sqlite3
from unittest.mock import patch

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

os.environ.setdefault("LLM_API_KEY", "test-key-not-used-because-mocked")

from fastapi.testclient import TestClient
from backend.main import app
from backend.database.repository import DatabaseUnavailableError
from backend.config import config
from backend.api.schemas import (
    AnalyzeResponse, Medication, InteractionResult, SafetyStatus, PatientSummary,
)

client = TestClient(app)


def test_health_endpoint():
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_local_frontend_origin_passes_cors_preflight():
    response = client.options(
        "/analyze",
        headers={
            "Origin": "http://localhost:5173",
            "Access-Control-Request-Method": "POST",
            "Access-Control-Request-Headers": "content-type",
        },
    )
    assert response.status_code == 200
    assert response.headers["access-control-allow-origin"] == "http://localhost:5173"


def test_analyze_empty_note_returns_400():
    response = client.post("/analyze", json={"clinical_note": ""})
    assert response.status_code == 400


def test_analyze_missing_field_returns_422():
    response = client.post("/analyze", json={})
    assert response.status_code == 422  # Pydantic validation error


def test_analyze_non_string_note_returns_422():
    response = client.post("/analyze", json={"clinical_note": ["warfarin"]})
    assert response.status_code == 422


def test_analyze_oversized_note_returns_422():
    response = client.post("/analyze", json={"clinical_note": "x" * 20001})
    assert response.status_code == 422
    assert "20000" in response.text


def test_analyze_valid_request_returns_200():
    fake_response = AnalyzeResponse(
        medications=[Medication(name="warfarin", dose="5 mg", frequency="once daily", route=None)],
        interactions=InteractionResult(pairs_checked=0, interactions_found=[], unmatched_drugs=[], highest_normalized_risk=None),
        safety=SafetyStatus(safety_level="none", show_critical_banner=False, banner_message=None),
        patient_summary=PatientSummary(
            explanation="You are taking one medication.",
            what_to_know=["No interactions were checked since only one medication was found."],
            next_step="Continue as directed by your doctor.",
        ),
        warnings=[],
    )

    with patch("backend.api.routes.run_pipeline", return_value=fake_response):
        response = client.post("/analyze", json={"clinical_note": "Patient takes warfarin 5mg daily."})

    assert response.status_code == 200
    body = response.json()
    assert body["medications"][0]["name"] == "warfarin"
    assert body["safety"]["safety_level"] == "none"


def test_analyze_backend_failure_returns_502():
    with patch("backend.api.routes.run_pipeline", side_effect=RuntimeError("LLM call failed")):
        response = client.post("/analyze", json={"clinical_note": "Patient takes warfarin."})

    assert response.status_code == 502


def test_analyze_database_failure_is_unavailable_not_no_interaction(caplog):
    note = "private clinical note sentinel that must not be logged"
    with patch("backend.api.routes.run_pipeline", side_effect=sqlite3.OperationalError("database is locked")):
        response = client.post("/analyze", json={"clinical_note": note})

    assert response.status_code == 503
    assert "No interaction check was completed" in response.json()["detail"]
    assert note not in caplog.text


def test_analyze_empty_ddinter_database_returns_actionable_503():
    error = DatabaseUnavailableError("The DDInter database has no interaction records. Load DDInter first.")
    with patch("backend.api.routes.run_pipeline", side_effect=error):
        response = client.post("/analyze", json={"clinical_note": "Patient takes two medicines."})

    assert response.status_code == 503
    assert "Load DDInter first" in response.json()["detail"]


def test_analyze_missing_llm_key_returns_actionable_503(monkeypatch):
    monkeypatch.setattr(config, "LLM_API_KEY", None)
    response = client.post("/analyze", json={"clinical_note": "Patient takes a medicine."})

    assert response.status_code == 503
    assert "LLM_API_KEY is missing" in response.json()["detail"]
