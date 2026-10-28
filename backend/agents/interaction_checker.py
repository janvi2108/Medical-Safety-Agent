"""
agents/interaction_checker.py
AGENT 2 - Interaction Checker

THE MOST SAFETY-CRITICAL FILE IN THE PROJECT.

This agent does not call an LLM at all. It is deliberately thin - it only
wires the extracted medication list into services/drug_database.py, which
does the real lookup work against DDInter 2.0. It's called an "agent"
because of its role in the pipeline (structured input from Agent 1,
structured output to Agent 3), not because it uses AI reasoning - it
explicitly does not, and cannot, since it has no import of the LLM client.
"""

from backend.api.schemas import ExtractionResult, InteractionResult
from backend.services.drug_database import DrugDatabaseService


def check_interactions(extraction: ExtractionResult) -> InteractionResult:
    medication_names = [m.name for m in extraction.medications]

    db_service = DrugDatabaseService()
    try:
        return db_service.check_all_pairs(medication_names)
    finally:
        db_service.close()
