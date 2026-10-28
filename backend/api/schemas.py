"""
api/schemas.py

All Pydantic models used across the API boundary and between pipeline
stages. One source of truth for what a "Medication" or "InteractionResult"
looks like - every agent and the API route import from here.
"""

from pydantic import BaseModel, Field, field_validator
from typing import Optional, Literal

MAX_CLINICAL_NOTE_LENGTH = 20_000


# ---------- Agent 1: Extraction ----------

class Medication(BaseModel):
    name: str = Field(..., min_length=1, description="Medication name exactly as written in the note")
    dose: Optional[str] = Field(None, description="Dose as written, e.g. '5 mg'")
    frequency: Optional[str] = Field(None, description="Frequency as written, e.g. 'once daily'")
    route: Optional[str] = Field(None, description="Route of administration, only if explicitly stated")

    @field_validator("name")
    @classmethod
    def name_must_contain_non_whitespace(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("Medication name must not be blank")
        return value


class ExtractionResult(BaseModel):
    medications: list[Medication]


# ---------- Agent 2: Interaction Checking ----------

class MatchStatus(BaseModel):
    """Whether a medication name could be confidently matched to a DDInter drug record."""
    drug_name: str
    matched: bool
    matched_name: Optional[str] = None  # canonical DDInter name, if matched


class InteractionRecord(BaseModel):
    drug_a: str
    drug_b: str
    source_risk: str = Field(..., description="Risk/severity value exactly as it appears in DDInter - never invented")
    normalized_risk: Literal["major", "moderate", "minor", "unknown"] = Field(
        ..., description="Our normalized bucket, mapped from source_risk - see docs/ddinter.md for the mapping"
    )
    mechanism: Optional[str] = None
    management: Optional[str] = None
    alternative_medications: Optional[str] = None
    source: str = "DDInter 2.0"


class InteractionResult(BaseModel):
    pairs_checked: int
    interactions_found: list[InteractionRecord]
    unmatched_drugs: list[MatchStatus] = Field(
        default_factory=list, description="Medications that could not be confidently matched to a DDInter record"
    )
    highest_normalized_risk: Optional[Literal["major", "moderate", "minor", "unknown"]] = None


# ---------- Safety Rule Engine ----------

SafetyLevel = Literal["none", "caution", "critical", "unverified"]


class SafetyStatus(BaseModel):
    safety_level: SafetyLevel
    show_critical_banner: bool
    banner_message: Optional[str] = None


# ---------- Agent 3: Patient Communication ----------

class PatientSummary(BaseModel):
    explanation: str
    what_to_know: list[str]
    next_step: str
    disclaimer: str = (
        "Educational prototype — not medical advice. Do not start, stop, or "
        "change medication based on this application. Consult a qualified "
        "healthcare professional."
    )


# ---------- API request/response ----------

class AnalyzeRequest(BaseModel):
    # No min_length constraint here on purpose: an empty/blank note should
    # produce the friendly "Please enter a clinical note." message from
    # api/routes.py (HTTP 400), not a generic Pydantic validation error (422).
    # A missing field entirely still correctly produces a 422.
    clinical_note: str = Field(
        ...,
        max_length=MAX_CLINICAL_NOTE_LENGTH,
        description=f"Free-text clinical note, up to {MAX_CLINICAL_NOTE_LENGTH} characters",
    )


class AnalyzeResponse(BaseModel):
    medications: list[Medication]
    interactions: InteractionResult
    safety: SafetyStatus
    patient_summary: Optional[PatientSummary] = None
    warnings: list[str] = Field(default_factory=list)
