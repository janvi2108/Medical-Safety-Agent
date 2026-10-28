"""
database/repository.py

Owns the actual database connection and all raw SQL. This is the ONLY file
in the project that knows whether it's talking to SQLite or PostgreSQL -
everything above it (services/drug_database.py) just calls repository
methods and doesn't care which database is underneath.

Locally: SQLite file (data/processed/ddinter/ddinter.db), zero setup.
Production: Azure Database for PostgreSQL, connection string from Key Vault.
"""

from backend.config import config
from backend.database.models import DrugRow, DrugInteractionRow, POSTGRES_SCHEMA, SQLITE_SCHEMA


class DatabaseUnavailableError(RuntimeError):
    """The database is reachable but cannot provide initialized DDInter data."""


class DrugRepository:
    def __init__(self):
        if not config.USE_SQLITE_FALLBACK and not config.DATABASE_URL:
            raise DatabaseUnavailableError(
                "DATABASE_URL is required when USE_SQLITE_FALLBACK=false. Configure a PostgreSQL connection "
                "or enable SQLite only for local development."
            )
        self._use_postgres = bool(config.DATABASE_URL) and not config.USE_SQLITE_FALLBACK
        if self._use_postgres:
            import psycopg2
            self._conn = psycopg2.connect(config.DATABASE_URL)
            self._ph = "%s"
        else:
            import sqlite3
            import os
            database_directory = os.path.dirname(config.SQLITE_PATH)
            if database_directory:
                os.makedirs(database_directory, exist_ok=True)
            self._conn = sqlite3.connect(config.SQLITE_PATH)
            self._ph = "?"

    # --- schema management ---

    def ensure_schema(self):
        schema = POSTGRES_SCHEMA if self._use_postgres else SQLITE_SCHEMA
        cursor = self._conn.cursor()
        for statement in schema.strip().split(";"):
            statement = statement.strip()
            if statement:
                cursor.execute(statement)
        self._conn.commit()

    def reset_schema(self):
        """Drops and recreates both tables - used by ingestion scripts for a clean reload."""
        cursor = self._conn.cursor()
        cursor.execute("DROP TABLE IF EXISTS drug_interactions")
        cursor.execute("DROP TABLE IF EXISTS drugs")
        self._conn.commit()
        self.ensure_schema()

    # --- drugs table ---

    def upsert_drug(self, name: str, normalized_name: str, source_identifier: str | None, atc_code: str | None) -> int:
        """Inserts a drug if it doesn't exist (by normalized_name), returns its id either way."""
        p = self._ph
        cursor = self._conn.cursor()
        cursor.execute(f"SELECT id FROM drugs WHERE normalized_name = {p}", (normalized_name,))
        row = cursor.fetchone()
        if row:
            return row[0]

        cursor.execute(
            f"INSERT INTO drugs (name, normalized_name, source_identifier, atc_code) VALUES ({p},{p},{p},{p})"
            + ("" if self._use_postgres else ""),
            (name, normalized_name, source_identifier, atc_code),
        )
        if self._use_postgres:
            cursor.execute("SELECT lastval()")
            return cursor.fetchone()[0]
        return cursor.lastrowid

    def find_drug_by_normalized_name(self, normalized_name: str) -> DrugRow | None:
        p = self._ph
        cursor = self._conn.cursor()
        cursor.execute(
            f"SELECT id, name, normalized_name, source_identifier, atc_code FROM drugs WHERE normalized_name = {p}",
            (normalized_name,),
        )
        row = cursor.fetchone()
        if row is None:
            return None
        return DrugRow(id=row[0], name=row[1], normalized_name=row[2], source_identifier=row[3], atc_code=row[4])

    # --- drug_interactions table ---

    def insert_interaction(self, drug_a_id: int, drug_b_id: int, source_risk: str, normalized_risk: str,
                            mechanism: str | None, management: str | None,
                            alternative_medications: str | None, source: str):
        """Caller must pass drug_a_id < drug_b_id (canonical ordering) - see services/drug_database.py."""
        assert drug_a_id < drug_b_id, "drug_a_id must be less than drug_b_id (canonical ordering)"
        p = self._ph
        cursor = self._conn.cursor()
        cursor.execute(
            f"""INSERT INTO drug_interactions
                (drug_a_id, drug_b_id, source_risk, normalized_risk, mechanism, management, alternative_medications, source)
                VALUES ({p},{p},{p},{p},{p},{p},{p},{p})
                {"ON CONFLICT (drug_a_id, drug_b_id) DO NOTHING" if self._use_postgres else ""}
            """,
            (drug_a_id, drug_b_id, source_risk, normalized_risk, mechanism, management, alternative_medications, source),
        )

    def find_interaction(self, drug_a_id: int, drug_b_id: int) -> DrugInteractionRow | None:
        """Caller must pass canonically-ordered IDs (a < b)."""
        p = self._ph
        cursor = self._conn.cursor()
        cursor.execute(
            f"""SELECT id, drug_a_id, drug_b_id, source_risk, normalized_risk, mechanism, management,
                       alternative_medications, source
                FROM drug_interactions
                WHERE drug_a_id = {p} AND drug_b_id = {p} AND source = 'DDInter 2.0'
                LIMIT 1
            """,
            (drug_a_id, drug_b_id),
        )
        row = cursor.fetchone()
        if row is None:
            return None
        return DrugInteractionRow(
            id=row[0], drug_a_id=row[1], drug_b_id=row[2], source_risk=row[3], normalized_risk=row[4],
            mechanism=row[5], management=row[6], alternative_medications=row[7], source=row[8],
        )

    def count_drugs(self) -> int:
        cursor = self._conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM drugs")
        return cursor.fetchone()[0]

    def count_interactions(self) -> int:
        cursor = self._conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM drug_interactions")
        return cursor.fetchone()[0]

    def count_ddinter_interactions(self) -> int:
        cursor = self._conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM drug_interactions WHERE source = 'DDInter 2.0'")
        return cursor.fetchone()[0]

    def commit(self):
        self._conn.commit()

    def rollback(self):
        self._conn.rollback()

    def close(self):
        self._conn.close()
