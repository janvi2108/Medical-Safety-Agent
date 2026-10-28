"""Agent 3: render DDInter findings without adding model-generated claims."""

from backend.api.schemas import InteractionResult, PatientSummary, SafetyStatus


def generate_patient_summary(interactions: InteractionResult, _safety: SafetyStatus) -> PatientSummary:
    """Build a patient-friendly summary solely from verified fields and lookup state."""
    if interactions.interactions_found:
        count = len(interactions.interactions_found)
        pair_word = "pair" if count == 1 else "pairs"
        explanation = (
            f"DDInter 2.0 contains recorded entries for {count} medication {pair_word}. "
            "These source classifications are not personalized clinical conclusions."
        )
        what_to_know = []
        for item in interactions.interactions_found:
            if item.normalized_risk == "unknown":
                what_to_know.append(
                    f"{item.drug_a} and {item.drug_b}: DDInter record found; severity unknown "
                    f"(recorded level: {item.source_risk})."
                )
            else:
                what_to_know.append(
                    f"{item.drug_a} and {item.drug_b}: DDInter classification: {item.source_risk}."
                )
    elif interactions.unmatched_drugs:
        explanation = "Some medication names could not be matched, so the interaction review is incomplete."
        what_to_know = [
            f"{item.drug_name} was not matched to a DDInter medication record and was not checked."
            for item in interactions.unmatched_drugs
        ]
    elif interactions.pairs_checked == 0:
        explanation = "Fewer than two matched medications were available, so no medication pair could be checked."
        what_to_know = []
    else:
        explanation = "No matching interaction record was found for the matched medication pairs checked."
        what_to_know = [
            "No matching record was found in the available DDInter dataset; this does not establish that the combination is safe."
        ]

    if interactions.unmatched_drugs and interactions.interactions_found:
        what_to_know.extend(
            f"{item.drug_name} was not matched and was not checked against the other medications."
            for item in interactions.unmatched_drugs
        )

    return PatientSummary(
        explanation=explanation,
        what_to_know=what_to_know,
        next_step="Discuss relevant findings with a qualified healthcare professional, such as a doctor or pharmacist.",
    )
