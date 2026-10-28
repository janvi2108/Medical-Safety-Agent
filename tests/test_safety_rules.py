"""
tests/test_safety_rules.py

Tests services/safety_rules.py directly - no LLM, no database, no mocking
needed, since this module is pure deterministic logic. This is exactly the
property that makes safety-critical decisions here rather than in the LLM:
these tests are simple and exhaustive because the logic is simple and
exhaustive.
"""

import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from backend.services.safety_rules import evaluate_safety
from backend.api.schemas import InteractionResult, InteractionRecord, MatchStatus


def _result(interactions=None, unmatched=None, highest=None):
    return InteractionResult(
        pairs_checked=1,
        interactions_found=interactions or [],
        unmatched_drugs=unmatched or [],
        highest_normalized_risk=highest,
    )


def test_major_interaction_produces_critical_banner():
    record = InteractionRecord(drug_a="Warfarin", drug_b="Aspirin", source_risk="Major", normalized_risk="major")
    status = evaluate_safety(_result(interactions=[record], highest="major"))

    assert status.safety_level == "critical"
    assert status.show_critical_banner is True
    assert status.banner_message is not None


def test_moderate_interaction_does_not_trigger_critical_banner():
    record = InteractionRecord(drug_a="Lisinopril", drug_b="Ibuprofen", source_risk="Moderate", normalized_risk="moderate")
    status = evaluate_safety(_result(interactions=[record], highest="moderate"))

    assert status.safety_level == "caution"
    assert status.show_critical_banner is False


def test_no_interaction_found_is_none_not_critical():
    status = evaluate_safety(_result(interactions=[], highest=None))

    assert status.safety_level == "none"
    assert status.show_critical_banner is False


def test_unmatched_drug_produces_unverified_status():
    unmatched = [MatchStatus(drug_name="MysteryDrug", matched=False, matched_name=None)]
    status = evaluate_safety(_result(unmatched=unmatched))

    assert status.safety_level == "unverified"
    assert "MysteryDrug" in status.banner_message


def test_critical_banner_cannot_be_suppressed_by_unrelated_input():
    """
    Regression test for the core safety principle: as long as a major
    interaction is present and every drug matched, the banner is always
    shown - there is no code path or parameter that turns it off.
    """
    record = InteractionRecord(drug_a="Warfarin", drug_b="Ibuprofen", source_risk="Major", normalized_risk="major")
    status = evaluate_safety(_result(interactions=[record], highest="major", unmatched=[]))

    assert status.show_critical_banner is True


def test_unknown_source_level_is_unverified_not_caution():
    status = evaluate_safety(_result(highest="unknown"))
    assert status.safety_level == "unverified"
    assert "severity is unknown" in status.banner_message


def test_recorded_levels_are_described_as_source_classifications():
    for level in ("Major", "Moderate"):
        status = evaluate_safety(_result(highest=level.lower()))
        assert f"{level} classification" in status.banner_message
        assert "patient's circumstances" in status.banner_message
