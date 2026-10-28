"""Ingest the supplied DDInter category CSVs without demo-data fallback.

Run from the project root with ``python -m scripts.load_ddinter``.
"""

import csv
from dataclasses import asdict, dataclass
from pathlib import Path
import sys

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from backend.config import config
from backend.database.repository import DrugRepository
from backend.services.drug_database import normalize_name

REQUIRED_COLUMNS = ("DDInterID_A", "Drug_A", "DDInterID_B", "Drug_B", "Level")
SOURCE = "DDInter 2.0"
RISK_NORMALIZATION = {"major": "major", "moderate": "moderate", "minor": "minor"}


@dataclass
class IngestionReport:
    files_processed: int = 0
    rows_read: int = 0
    rows_imported: int = 0
    rows_rejected: int = 0
    rows_skipped_duplicate: int = 0
    drugs_in_database: int = 0
    interactions_in_database: int = 0
    ddinter_interactions_in_database: int = 0


def discover_csv_files(directory: str | Path | None = None) -> list[Path]:
    """Find only original DDInter category files; never substitute demo data."""
    root = Path(directory or config.RAW_DDINTER_DIR)
    files = sorted(root.glob("ddinter_downloads_code_*.csv"))
    if not files:
        raise FileNotFoundError(
            f"No supplied DDInter CSV files found in {root}. "
            "Expected ddinter_downloads_code_*.csv; synthetic demo data is not used."
        )
    return files


def validate_header(fieldnames: list[str] | None, path: Path) -> None:
    if fieldnames is None or set(fieldnames) != set(REQUIRED_COLUMNS) or len(fieldnames) != len(REQUIRED_COLUMNS):
        raise ValueError(
            f"Unexpected columns in {path.name}: {fieldnames!r}; "
            f"expected exactly {list(REQUIRED_COLUMNS)!r}"
        )


def _valid_row(row: dict[str, str | None]) -> bool:
    values = [row.get(column) for column in REQUIRED_COLUMNS]
    if any(value is None or not value.strip() for value in values):
        return False
    id_a, name_a, id_b, name_b, _level = (value.strip() for value in values)
    return (
        id_a.startswith("DDInter") and id_b.startswith("DDInter")
        and normalize_name(name_a) and normalize_name(name_b)
        and id_a != id_b and normalize_name(name_a) != normalize_name(name_b)
    )


def load(directory: str | Path | None = None, repository: DrugRepository | None = None) -> IngestionReport:
    files = discover_csv_files(directory)
    repo = repository or DrugRepository()
    report = IngestionReport(files_processed=len(files))
    seen_pairs: dict[tuple[str, str], str] = {}
    owns_repository = repository is None
    try:
        repo.ensure_schema()
        for path in files:
            with path.open("r", encoding="utf-8-sig", newline="") as handle:
                reader = csv.DictReader(handle)
                validate_header(reader.fieldnames, path)
                for line_number, row in enumerate(reader, start=2):
                    report.rows_read += 1
                    # DictReader puts surplus fields under a None key.
                    if None in row or not _valid_row(row):
                        report.rows_rejected += 1
                        continue
                    id_a = row["DDInterID_A"].strip()
                    name_a = row["Drug_A"].strip()
                    id_b = row["DDInterID_B"].strip()
                    name_b = row["Drug_B"].strip()
                    source_risk = row["Level"].strip()
                    pair = tuple(sorted((id_a, id_b)))
                    previous_risk = seen_pairs.get(pair)
                    if previous_risk is not None:
                        if previous_risk != source_risk:
                            raise ValueError(
                                f"Conflicting Level for DDInter pair {pair} at {path.name}:{line_number}: "
                                f"{previous_risk!r} vs {source_risk!r}"
                            )
                        report.rows_skipped_duplicate += 1
                        continue
                    seen_pairs[pair] = source_risk

                    drug_a_id = repo.upsert_drug(
                        name=name_a, normalized_name=normalize_name(name_a),
                        source_identifier=id_a, atc_code=None,
                    )
                    drug_b_id = repo.upsert_drug(
                        name=name_b, normalized_name=normalize_name(name_b),
                        source_identifier=id_b, atc_code=None,
                    )
                    if drug_a_id == drug_b_id:
                        report.rows_rejected += 1
                        continue
                    canonical_a, canonical_b = sorted((drug_a_id, drug_b_id))
                    existing = repo.find_interaction(canonical_a, canonical_b)
                    if existing:
                        if existing.source != SOURCE or existing.source_risk != source_risk:
                            raise ValueError(
                                f"Existing non-DDInter or conflicting database record for {pair}; "
                                "database left unchanged by rollback."
                            )
                        report.rows_skipped_duplicate += 1
                        continue
                    risk_key = source_risk.lower()
                    repo.insert_interaction(
                        drug_a_id=canonical_a, drug_b_id=canonical_b,
                        source_risk=source_risk,
                        normalized_risk=RISK_NORMALIZATION.get(risk_key, "unknown"),
                        mechanism=None, management=None, alternative_medications=None,
                        source=SOURCE,
                    )
                    report.rows_imported += 1
        repo.commit()
        report.drugs_in_database = repo.count_drugs()
        report.interactions_in_database = repo.count_interactions()
        report.ddinter_interactions_in_database = repo.count_ddinter_interactions()
        return report
    except Exception:
        repo.rollback()
        raise
    finally:
        if owns_repository:
            repo.close()


if __name__ == "__main__":
    print(asdict(load()))
