import csv
from pathlib import Path

import pytest

from backend.config import config
from backend.database.repository import DrugRepository
from backend.services.drug_database import DrugDatabaseService, normalize_name
from scripts.load_ddinter import REQUIRED_COLUMNS, discover_csv_files, load, validate_header

PROJECT_ROOT = Path(__file__).resolve().parents[1]
RAW_DATA_DIR = PROJECT_ROOT / "data" / "raw" / "ddinter"


def _temporary_repo(path, monkeypatch):
    monkeypatch.setattr(config, "DATABASE_URL", None)
    monkeypatch.setattr(config, "USE_SQLITE_FALLBACK", True)
    monkeypatch.setattr(config, "SQLITE_PATH", str(path))
    return DrugRepository()


def test_all_eight_supplied_files_have_expected_schema():
    files = discover_csv_files(RAW_DATA_DIR)
    assert len(files) == 8
    assert {path.name[-5] for path in files} == set("ABDH LPRV".replace(" ", ""))
    for path in files:
        with path.open(encoding="utf-8-sig", newline="") as handle:
            reader = csv.DictReader(handle)
            validate_header(reader.fieldnames, path)
            assert next(reader, None) is not None


def test_actual_dataset_import_is_traceable_and_repeatable(tmp_path, monkeypatch):
    repo = _temporary_repo(tmp_path / "ddinter.db", monkeypatch)
    files = discover_csv_files(RAW_DATA_DIR)
    expected_source_rows = 0
    source_example = None
    for path in files:
        with path.open(encoding="utf-8-sig", newline="") as handle:
            reader = csv.DictReader(handle)
            rows = list(reader)
        expected_source_rows += len(rows)
        if source_example is None:
            source_example = rows[0]

    first = load(RAW_DATA_DIR, repo)
    assert first.rows_read == expected_source_rows == 222383
    assert first.rows_rejected == 0
    assert first.rows_skipped_duplicate == 62148
    assert first.rows_imported == 160235
    assert first.ddinter_interactions_in_database == 160235
    assert first.drugs_in_database == 1939

    drug_a = repo.find_drug_by_normalized_name(normalize_name(source_example["Drug_A"]))
    drug_b = repo.find_drug_by_normalized_name(normalize_name(source_example["Drug_B"]))
    assert drug_a and drug_a.source_identifier == source_example["DDInterID_A"]
    assert drug_b and drug_b.source_identifier == source_example["DDInterID_B"]
    interaction = repo.find_interaction(*sorted((drug_a.id, drug_b.id)))
    assert interaction is not None
    assert interaction.source_risk == source_example["Level"]
    assert interaction.source == "DDInter 2.0"
    assert interaction.mechanism is None  # not present in supplied CSVs

    checker = DrugDatabaseService()
    try:
        found = checker.check_all_pairs([source_example["Drug_B"], source_example["Drug_A"]])
    finally:
        checker.close()
    assert len(found.interactions_found) == 1
    assert found.interactions_found[0].source_risk == source_example["Level"]

    second = load(RAW_DATA_DIR, repo)
    assert second.rows_imported == 0
    assert second.rows_skipped_duplicate == expected_source_rows
    assert repo.count_ddinter_interactions() == 160235
    repo.close()


def test_missing_source_files_do_not_fall_back_to_demo(tmp_path):
    (tmp_path / "synthetic_demo_data.csv").write_text("demo", encoding="utf-8")
    with pytest.raises(FileNotFoundError, match="synthetic demo data is not used"):
        discover_csv_files(tmp_path)


def test_schema_validation_rejects_unrecognized_columns(tmp_path):
    with pytest.raises(ValueError, match="Unexpected columns"):
        validate_header(["Drug_A", "Drug_B", "Level"], tmp_path / "bad.csv")


def test_malformed_rows_are_counted_and_valid_rows_are_kept(tmp_path, monkeypatch):
    path = tmp_path / "ddinter_downloads_code_T.csv"
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(REQUIRED_COLUMNS)
        writer.writerow(["DDInter1", "Drug One", "DDInter2", "Drug Two", "Moderate"])
        writer.writerow(["", "Missing ID", "DDInter2", "Drug Two", "Major"])
    repo = _temporary_repo(tmp_path / "isolated.db", monkeypatch)
    report = load(tmp_path, repo)
    assert report.rows_read == 2
    assert report.rows_imported == 1
    assert report.rows_rejected == 1
    assert repo.count_ddinter_interactions() == 1
    repo.close()
