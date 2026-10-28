"""
agents/orchestrator.py

Wires the three agents and the safety rule engine into one pipeline call.
This is the only place that knows the overall pipeline order - individual
agents don't call each other directly, which keeps them independently
testable (see tests/test_extractor.py, test_interactions.py, test_safety_rules.py).

Flow:
    clinical note
        -> Agent 1 (extractor)
        -> Agent 2 (interaction_checker, DB lookup only)
        -> safety_rules.evaluate_safety (deterministic)
        -> Agent 3 (patient_communicator)
        -> AnalyzeResponse
"""

from backend.api.schemas import AnalyzeResponse, InteractionResult
from backend.agents.extractor import extract_medications
from backend.agents.interaction_checker import check_interactions
from backend.agents.patient_communicator import generate_patient_summary
from backend.services.safety_rules import evaluate_safety


def run_pipeline(clinical_note: str) -> AnalyzeResponse:
    warnings: list[str] = []

    extraction = extract_medications(clinical_note)

    if len(extraction.medications) == 0:
        warnings.append("No medications were found in this note.")

    # Resolve even a single medication so unknown names are not silently treated as checked.
    interactions = check_interactions(extraction) if extraction.medications else InteractionResult(
        pairs_checked=0, interactions_found=[], unmatched_drugs=[], highest_normalized_risk=None
    )

    safety = evaluate_safety(interactions)

    summary = None
    if len(extraction.medications) > 0:
        summary = generate_patient_summary(interactions, safety)

    return AnalyzeResponse(
        medications=extraction.medications,
        interactions=interactions,
        safety=safety,
        patient_summary=summary,
        warnings=warnings,
    )
