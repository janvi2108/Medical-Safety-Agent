"""
tests/test_extractor.py

Tests the extractor's contract using a fake LLM provider - these tests
never make a real network call, so they run without an API key and are
deterministic (unlike the real LLM, which can vary its output).
"""

import sys
import os
import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from backend.api.schemas import ExtractionResult, Medication


def _fake_extraction(medications_json: list[dict]) -> ExtractionResult:
    """Simulates what extract_medications() would return, without calling an LLM."""
    return ExtractionResult(medications=[Medication(**m) for m in medications_json])


def test_single_medication():
    result = _fake_extraction([{"name": "metformin", "dose": "500 mg", "frequency": "twice daily", "route": None}])
    assert len(result.medications) == 1
    assert result.medications[0].name == "metformin"


def test_multiple_medications():
    result = _fake_extraction([
        {"name": "warfarin", "dose": "5 mg", "frequency": "once daily", "route": None},
        {"name": "aspirin", "dose": "81 mg", "frequency": "once daily", "route": None},
    ])
    assert len(result.medications) == 2


def test_missing_dose_is_none_not_guessed():
    result = _fake_extraction([{"name": "warfarin", "dose": None, "frequency": None, "route": None}])
    assert result.medications[0].dose is None


def test_empty_note_raises():
    from backend.agents.extractor import extract_medications
    with pytest.raises(ValueError):
        extract_medications("")


def test_medication_schema_rejects_missing_name():
    with pytest.raises(Exception):
        Medication(dose="5 mg")  # name is required


def test_medication_schema_rejects_blank_name():
    with pytest.raises(Exception):
        Medication(name="   ")


def test_malformed_llm_output_is_reported_as_provider_failure(monkeypatch):
    from backend.agents import extractor

    class FakeLLM:
        def get_json_completion(self, *_args, **_kwargs):
            return {"medications": "not-a-list"}

    monkeypatch.setattr(extractor, "get_llm_client", lambda: FakeLLM())
    monkeypatch.setattr(extractor, "_load_prompt", lambda: "test prompt")
    with pytest.raises(RuntimeError, match="malformed structured data"):
        extractor.extract_medications("Patient takes a medication.")


def test_missing_llm_key_has_actionable_configuration_error(monkeypatch):
    from backend.agents import extractor
    from backend.services.llm import llm_client

    monkeypatch.setattr(llm_client.config, "LLM_API_KEY", None)
    with pytest.raises(llm_client.LLMConfigurationError, match="repository-root .env"):
        extractor.extract_medications("Patient takes a medication.")


def test_successful_extraction_uses_mocked_llm_response(monkeypatch):
    from backend.agents import extractor

    class FakeLLM:
        def get_json_completion(self, *_args, **_kwargs):
            return {"medications": [{"name": "metformin", "dose": "500 mg", "frequency": "twice daily", "route": "oral"}]}

    monkeypatch.setattr(extractor, "get_llm_client", lambda: FakeLLM())
    monkeypatch.setattr(extractor, "_load_prompt", lambda: "test prompt")
    result = extractor.extract_medications("Patient takes metformin 500 mg twice daily by mouth.")

    assert result.medications[0].name == "metformin"
    assert result.medications[0].dose == "500 mg"
    assert result.medications[0].frequency == "twice daily"
    assert result.medications[0].route == "oral"


def test_invalid_medication_data_fails_without_fake_results(monkeypatch):
    from backend.agents import extractor

    class FakeLLM:
        def get_json_completion(self, *_args, **_kwargs):
            return {"medications": [{"name": "   "}]}

    monkeypatch.setattr(extractor, "get_llm_client", lambda: FakeLLM())
    monkeypatch.setattr(extractor, "_load_prompt", lambda: "test prompt")
    with pytest.raises(RuntimeError, match="malformed structured data"):
        extractor.extract_medications("Patient takes a medication.")
