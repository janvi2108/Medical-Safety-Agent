"""
scripts/init_db.py

Creates the database schema (drugs + drug_interactions tables) without
loading any data. Safe to run before ingestion; existing rows are preserved.

Usage:
    python -m scripts.init_db
"""

from pathlib import Path
import sys

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from backend.database.repository import DrugRepository


def main():
    repo = DrugRepository()
    try:
        repo.ensure_schema()
        print("Schema created (or already existed).")
        print(f"Drugs table rows: {repo.count_drugs()}")
        print(f"Interactions table rows: {repo.count_interactions()}")
    finally:
        repo.close()


if __name__ == "__main__":
    main()
