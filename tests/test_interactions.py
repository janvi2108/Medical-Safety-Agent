"""
tests/test_interactions.py

Tests services/drug_database.py against a temporary, seeded SQLite database -
no real DDInter data or network access needed. Covers exact match,
capitalization/whitespace normalization, unknown drugs, known interactions,
reversed pairs, multiple pairs, and duplicate pair handling.
"""

import sys
import os
import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))


@pytest.fixture
def seeded_db(tmp_path, monkeypatch):
    from backend.config import config

    monkeypatch.setattr(config, "DATABASE_URL", None)
    monkeypatch.setattr(config, "USE_SQLITE_FALLBACK", True)
    monkeypatch.setattr(config, "SQLITE_PATH", str(tmp_path / "test.db"))

    from backend.database.repository import DrugRepository
    repo = DrugRepository()
    repo.ensure_schema()

    id_warfarin = repo.upsert_drug("Warfarin", "warfarin", None, None)
    id_aspirin = repo.upsert_drug("Aspirin", "aspirin", None, None)
    id_metformin = repo.upsert_drug("Metformin", "metformin", None, None)

    a, b = sorted([id_warfarin, id_aspirin])
    repo.insert_interaction(
        drug_a_id=a, drug_b_id=b, source_risk="Major", normalized_risk="major",
        mechanism="Increased bleeding risk", management="Monitor INR closely", alternative_medications=None,
        source="DDInter 2.0",
    )
    repo.commit()
    repo.close()
    return tmp_path


def test_known_interaction_found(seeded_db):
    from backend.services.drug_database import DrugDatabaseService
    service = DrugDatabaseService()
    result = service.check_all_pairs(["Warfarin", "Aspirin"])
    service.close()

    assert result.pairs_checked == 1
    assert len(result.interactions_found) == 1
    assert result.interactions_found[0].normalized_risk == "major"
    assert result.highest_normalized_risk == "major"


@pytest.mark.parametrize(
    ("source_risk", "normalized_risk"),
    [("Moderate", "moderate"), ("Minor", "minor"), ("Unknown", "unknown")],
)
def test_recorded_source_classification_is_preserved(seeded_db, source_risk, normalized_risk):
    from backend.config import config
    from backend.database.repository import DrugRepository
    from backend.services.drug_database import DrugDatabaseService

    repo = DrugRepository()
    first_id = repo.upsert_drug("Fixture Alpha", "fixture alpha", "DDInter9001", None)
    second_id = repo.upsert_drug("Fixture Beta", "fixture beta", "DDInter9002", None)
    first_id, second_id = sorted((first_id, second_id))
    repo.insert_interaction(
        drug_a_id=first_id,
        drug_b_id=second_id,
        source_risk=source_risk,
        normalized_risk=normalized_risk,
        mechanism=None,
        management=None,
        alternative_medications=None,
        source="DDInter 2.0",
    )
    repo.commit()
    repo.close()

    service = DrugDatabaseService()
    try:
        result = service.check_all_pairs(["Fixture Alpha", "Fixture Beta"])
    finally:
        service.close()

    assert result.interactions_found[0].source_risk == source_risk
    assert result.interactions_found[0].normalized_risk == normalized_risk


def test_reversed_pair_still_matches(seeded_db):
    from backend.services.drug_database import DrugDatabaseService
    service = DrugDatabaseService()
    result = service.check_all_pairs(["Aspirin", "Warfarin"])  # reversed order
    service.close()

    assert len(result.interactions_found) == 1


def test_capitalization_and_whitespace_normalized(seeded_db):
    from backend.services.drug_database import DrugDatabaseService
    service = DrugDatabaseService()
    result = service.check_all_pairs(["  WARFARIN  ", "aspirin"])
    service.close()

    assert len(result.interactions_found) == 1


def test_no_interaction_between_unrelated_drugs(seeded_db):
    from backend.services.drug_database import DrugDatabaseService
    service = DrugDatabaseService()
    result = service.check_all_pairs(["Warfarin", "Metformin"])
    service.close()

    assert len(result.interactions_found) == 0
    assert result.highest_normalized_risk is None


def test_unknown_drug_reported_as_unmatched(seeded_db):
    from backend.services.drug_database import DrugDatabaseService
    service = DrugDatabaseService()
    result = service.check_all_pairs(["Warfarin", "SomeUnknownDrugXYZ"])
    service.close()

    unmatched_names = [m.drug_name for m in result.unmatched_drugs]
    assert "SomeUnknownDrugXYZ" in unmatched_names


def test_single_unknown_medication_is_still_matched_or_reported(seeded_db):
    from backend.services.drug_database import DrugDatabaseService
    service = DrugDatabaseService()
    result = service.check_all_pairs(["SingleUnknownMedication"])
    service.close()
    assert result.pairs_checked == 0
    assert [item.drug_name for item in result.unmatched_drugs] == ["SingleUnknownMedication"]


def test_multiple_pairs_generates_n_choose_2(seeded_db):
    from backend.services.drug_database import DrugDatabaseService
    service = DrugDatabaseService()
    result = service.check_all_pairs(["Warfarin", "Aspirin", "Metformin"])
    service.close()

    # 3 medications -> 3 unique pairs (3*2/2)
    assert result.pairs_checked == 3


def test_duplicate_medication_in_list_does_not_double_count(seeded_db):
    from backend.services.drug_database import DrugDatabaseService
    service = DrugDatabaseService()
    result = service.check_all_pairs(["Warfarin", "Warfarin", "Aspirin"])
    service.close()

    # de-duped to 2 unique names -> 1 pair, not 3
    assert result.pairs_checked == 1


def test_empty_ddinter_database_fails_closed_with_load_instructions(tmp_path, monkeypatch):
    from backend.config import config
    from backend.database.repository import DatabaseUnavailableError
    from backend.database.repository import DrugRepository
    from backend.services.drug_database import DrugDatabaseService

    monkeypatch.setattr(config, "DATABASE_URL", None)
    monkeypatch.setattr(config, "USE_SQLITE_FALLBACK", True)
    monkeypatch.setattr(config, "SQLITE_PATH", str(tmp_path / "empty.db"))
    repo = DrugRepository()
    repo.ensure_schema()
    repo.close()

    service = DrugDatabaseService()
    try:
        with pytest.raises(DatabaseUnavailableError, match="python -m scripts.load_ddinter"):
            service.check_all_pairs(["Warfarin", "Aspirin"])
    finally:
        service.close()


def test_postgres_mode_requires_database_url(monkeypatch):
    from backend.config import config
    from backend.database.repository import DatabaseUnavailableError, DrugRepository

    monkeypatch.setattr(config, "DATABASE_URL", None)
    monkeypatch.setattr(config, "USE_SQLITE_FALLBACK", False)
    with pytest.raises(DatabaseUnavailableError, match="DATABASE_URL is required"):
        DrugRepository()


def test_schema_initialization_is_repeatable_in_temporary_database(tmp_path, monkeypatch, capsys):
    from backend.config import config
    from scripts.init_db import main

    monkeypatch.setattr(config, "DATABASE_URL", None)
    monkeypatch.setattr(config, "USE_SQLITE_FALLBACK", True)
    monkeypatch.setattr(config, "SQLITE_PATH", str(tmp_path / "initialized.db"))

    main()
    first_output = capsys.readouterr().out
    main()
    second_output = capsys.readouterr().out

    assert first_output == second_output
    assert "Schema created (or already existed)." in second_output
