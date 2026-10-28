"""
database/models.py

Row models and schema DDL for the normalized DDInter schema.

Design (see docs/database.md for full explanation):

  drugs
  -----
  id, name, normalized_name, source_identifier, atc_code, created_at

  drug_interactions
  ------------------
  id, drug_a_id, drug_b_id, source_risk, normalized_risk, mechanism,
  management, alternative_medications, source, created_at

Canonical pair ordering: drug_a_id is always < drug_b_id. This means
"warfarin + aspirin" and "aspirin + warfarin" always resolve to exactly one
row, never two - the repository layer sorts IDs before every insert and
every lookup, so no other code needs to think about ordering.
"""

from dataclasses import dataclass
from datetime import datetime
from typing import Optional


@dataclass
class DrugRow:
    id: Optional[int]
    name: str
    normalized_name: str
    source_identifier: Optional[str]
    atc_code: Optional[str]
    created_at: Optional[datetime] = None


@dataclass
class DrugInteractionRow:
    id: Optional[int]
    drug_a_id: int
    drug_b_id: int
    source_risk: str
    normalized_risk: str
    mechanism: Optional[str]
    management: Optional[str]
    alternative_medications: Optional[str]
    source: str
    created_at: Optional[datetime] = None


# --- Schema DDL ---
# Two dialects because local dev uses SQLite (zero setup) and production
# uses PostgreSQL (Azure Database for PostgreSQL). Written to be as close
# to identical as the two dialects allow.

POSTGRES_SCHEMA = """
CREATE TABLE IF NOT EXISTS drugs (
    id SERIAL PRIMARY KEY,
    name TEXT NOT NULL,
    normalized_name TEXT NOT NULL UNIQUE,
    source_identifier TEXT,
    atc_code TEXT,
    created_at TIMESTAMP DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS drug_interactions (
    id SERIAL PRIMARY KEY,
    drug_a_id INTEGER NOT NULL REFERENCES drugs(id),
    drug_b_id INTEGER NOT NULL REFERENCES drugs(id),
    source_risk TEXT NOT NULL,
    normalized_risk TEXT NOT NULL,
    mechanism TEXT,
    management TEXT,
    alternative_medications TEXT,
    source TEXT NOT NULL DEFAULT 'DDInter 2.0',
    created_at TIMESTAMP DEFAULT NOW(),
    CONSTRAINT canonical_pair CHECK (drug_a_id < drug_b_id),
    CONSTRAINT unique_pair UNIQUE (drug_a_id, drug_b_id)
);

CREATE INDEX IF NOT EXISTS idx_drugs_normalized_name ON drugs(normalized_name);
CREATE INDEX IF NOT EXISTS idx_interactions_drug_a ON drug_interactions(drug_a_id);
CREATE INDEX IF NOT EXISTS idx_interactions_drug_b ON drug_interactions(drug_b_id);
"""

SQLITE_SCHEMA = """
CREATE TABLE IF NOT EXISTS drugs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    normalized_name TEXT NOT NULL UNIQUE,
    source_identifier TEXT,
    atc_code TEXT,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS drug_interactions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    drug_a_id INTEGER NOT NULL REFERENCES drugs(id),
    drug_b_id INTEGER NOT NULL REFERENCES drugs(id),
    source_risk TEXT NOT NULL,
    normalized_risk TEXT NOT NULL,
    mechanism TEXT,
    management TEXT,
    alternative_medications TEXT,
    source TEXT NOT NULL DEFAULT 'DDInter 2.0',
    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
    CHECK (drug_a_id < drug_b_id),
    UNIQUE (drug_a_id, drug_b_id)
);

CREATE INDEX IF NOT EXISTS idx_drugs_normalized_name ON drugs(normalized_name);
CREATE INDEX IF NOT EXISTS idx_interactions_drug_a ON drug_interactions(drug_a_id);
CREATE INDEX IF NOT EXISTS idx_interactions_drug_b ON drug_interactions(drug_b_id);
"""
