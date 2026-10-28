"""
services/safety_rules.py

Deterministic safety rule engine - pure Python logic, zero LLM dependency.
This module never imports anything from services/llm/, so there is no way
for a model call to influence whether a critical warning is shown.

Rules are based on `normalized_risk`, which is OUR mapping on top of
DDInter's original `source_risk` values (see docs/ddinter.md for exactly
how that mapping is defined - it is documented, not invented ad hoc).
"""

from backend.api.schemas import InteractionResult, SafetyStatus


def evaluate_safety(interaction_result: InteractionResult) -> SafetyStatus:
    risk = interaction_result.highest_normalized_risk

    if risk == "major":
        return SafetyStatus(
            safety_level="critical",
            show_critical_banner=True,
            banner_message=(
                "DDInter records a Major classification for this pair. Its clinical significance depends on the patient's circumstances; review it with a doctor or pharmacist."
            ),
        )

    if risk == "moderate":
        return SafetyStatus(
            safety_level="caution",
            show_critical_banner=False,
            banner_message="DDInter records a Moderate classification for this pair. Its clinical significance depends on the patient's circumstances; review it with a doctor or pharmacist.",
        )

    if risk in ("minor", "unknown"):
        if risk == "unknown":
            return SafetyStatus(
                safety_level="unverified", show_critical_banner=False,
                banner_message="A DDInter record was found, but its source severity is unknown.",
            )
        return SafetyStatus(safety_level="caution", show_critical_banner=False, banner_message=None)

    # Preserve positive database findings above; otherwise an unknown name
    # means the pair check is incomplete, not a clean result.
    if interaction_result.unmatched_drugs:
        names = ", ".join(m.drug_name for m in interaction_result.unmatched_drugs)
        return SafetyStatus(
            safety_level="unverified",
            show_critical_banner=False,
            banner_message=f"These medication(s) could not be matched to DDInter 2.0 and were not checked: {names}.",
        )

    # No interaction found at all - explicitly NOT the same claim as "safe"
    return SafetyStatus(safety_level="none", show_critical_banner=False, banner_message=None)
