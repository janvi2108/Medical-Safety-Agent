from backend.agents.patient_communicator import generate_patient_summary
from backend.api.schemas import InteractionRecord, InteractionResult, MatchStatus, SafetyStatus


def test_patient_summary_only_states_verified_pair_and_source_level():
    result = InteractionResult(
        pairs_checked=1,
        interactions_found=[InteractionRecord(
            drug_a="Drug A", drug_b="Drug B", source_risk="Moderate",
            normalized_risk="moderate", source="DDInter 2.0",
        )],
        unmatched_drugs=[],
        highest_normalized_risk="moderate",
    )
    summary = generate_patient_summary(
        result,
        SafetyStatus(safety_level="caution", show_critical_banner=False, banner_message=None),
    )
    assert "Drug A and Drug B" in summary.what_to_know[0]
    assert "Moderate" in summary.what_to_know[0]
    assert "DDInter classification: Moderate" in summary.what_to_know[0]
    assert "not personalized clinical conclusions" in summary.explanation
    assert "qualified healthcare professional" in summary.next_step
    assert "Educational prototype" in summary.disclaimer
    patient_text = " ".join([summary.explanation, *summary.what_to_know, summary.next_step])
    assert "personalized clinical risk" not in patient_text.lower()
    assert "definitely" not in patient_text.lower()
    assert "should stop" not in patient_text.lower()
    assert summary.next_step


def test_patient_summary_distinguishes_no_record_and_unknown_medication():
    safety = SafetyStatus(safety_level="none", show_critical_banner=False, banner_message=None)
    no_record = generate_patient_summary(
        InteractionResult(pairs_checked=1, interactions_found=[], unmatched_drugs=[], highest_normalized_risk=None), safety
    )
    unknown = generate_patient_summary(
        InteractionResult(
            pairs_checked=0, interactions_found=[],
            unmatched_drugs=[MatchStatus(drug_name="Mystery", matched=False)], highest_normalized_risk=None,
        ),
        SafetyStatus(safety_level="unverified", show_critical_banner=False, banner_message="Mystery was not matched."),
    )
    assert "No matching interaction record" in no_record.explanation
    assert "not establish" in no_record.what_to_know[0]
    assert "incomplete" in unknown.explanation
    assert "Mystery" in unknown.what_to_know[0]


def test_recorded_unknown_is_not_confused_with_no_matching_record():
    safety = SafetyStatus(safety_level="unverified", show_critical_banner=False, banner_message=None)
    recorded_unknown = generate_patient_summary(
        InteractionResult(
            pairs_checked=1,
            interactions_found=[InteractionRecord(
                drug_a="Drug A", drug_b="Drug B", source_risk="Unknown",
                normalized_risk="unknown", source="DDInter 2.0",
            )],
            unmatched_drugs=[],
            highest_normalized_risk="unknown",
        ),
        safety,
    )
    no_matching_record = generate_patient_summary(
        InteractionResult(pairs_checked=1, interactions_found=[], unmatched_drugs=[], highest_normalized_risk=None),
        SafetyStatus(safety_level="none", show_critical_banner=False, banner_message=None),
    )

    assert "record found; severity unknown" in recorded_unknown.what_to_know[0]
    assert "No matching record" not in recorded_unknown.what_to_know[0]
    assert "No matching record was found" in no_matching_record.what_to_know[0]
    assert "does not establish" in no_matching_record.what_to_know[0]
