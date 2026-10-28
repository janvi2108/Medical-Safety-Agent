"""
services/drug_database.py

Sits between Agent 2 and database/repository.py. This is where the
"database-grounded, not LLM-guessed" principle is structurally enforced:
this module never imports the LLM client, so there is no code path by
which an interaction fact could come from anywhere but the database.

Responsibilities:
  - normalize drug names (case, whitespace) before lookup
  - resolve common aliases (brand names -> generic names)
  - if a name can't be confidently matched, report it as unmatched rather
    than guessing (see docs/ddinter.md, section "Drug Normalization")
  - generate canonical (a_id < b_id) pairs so "warfarin+aspirin" and
    "aspirin+warfarin" always hit the same row
"""

from itertools import combinations
from backend.database.repository import DatabaseUnavailableError, DrugRepository
from backend.api.schemas import InteractionRecord, InteractionResult, MatchStatus

# Small alias table for common naming variations. Extend this as you
# encounter more real-world note variations after loading the real dataset.
_ALIASES = {
    "tylenol": "acetaminophen",
    "advil": "ibuprofen",
    "motrin": "ibuprofen",
    "coumadin": "warfarin",
    "glucophage": "metformin",
}

_RISK_RANK = {"major": 3, "moderate": 2, "minor": 1, "unknown": 0}


def normalize_name(name: str) -> str:
    cleaned = " ".join(name.strip().lower().split())  # collapse internal whitespace too
    return _ALIASES.get(cleaned, cleaned)


class DrugDatabaseService:
    def __init__(self):
        self._repo = DrugRepository()

    def check_all_pairs(self, medication_names: list[str]) -> InteractionResult:
        """
        Generates every unique pair from the medication list, resolves each
        drug to a database record (or marks it unmatched), and looks up
        interactions only for pairs where BOTH drugs matched.

        No LLM call happens anywhere in this method or anything it calls.
        """
        unique_names = list(dict.fromkeys(medication_names))  # de-dupe, preserve order

        try:
            interaction_count = self._repo.count_ddinter_interactions()
        except Exception as exc:
            raise DatabaseUnavailableError(
                "The interaction database is not initialized. Run `python -m scripts.init_db` "
                "and `python -m scripts.load_ddinter` from the project root."
            ) from exc
        if interaction_count == 0:
            raise DatabaseUnavailableError(
                "The DDInter database has no interaction records. Run `python -m scripts.load_ddinter` "
                "from the project root before analyzing notes."
            )

        # Resolve each name to a drug record once, up front
        resolved = {}
        unmatched: list[MatchStatus] = []
        for name in unique_names:
            norm = normalize_name(name)
            drug = self._repo.find_drug_by_normalized_name(norm)
            if drug is None:
                unmatched.append(MatchStatus(drug_name=name, matched=False, matched_name=None))
            else:
                resolved[name] = drug
                unmatched.append(MatchStatus(drug_name=name, matched=True, matched_name=drug.name))

        matched_names = list(resolved.keys())
        pairs = list(combinations(matched_names, 2))  # N(N-1)/2 pairs among matched drugs only

        found: list[InteractionRecord] = []
        for name_a, name_b in pairs:
            drug_a, drug_b = resolved[name_a], resolved[name_b]
            if drug_a.id == drug_b.id:
                continue  # same underlying drug listed under two names - not a real pair
            a_id, b_id = sorted([drug_a.id, drug_b.id])  # canonical ordering

            row = self._repo.find_interaction(a_id, b_id)
            if row:
                found.append(InteractionRecord(
                    drug_a=drug_a.name,
                    drug_b=drug_b.name,
                    source_risk=row.source_risk,
                    normalized_risk=row.normalized_risk,
                    mechanism=row.mechanism,
                    management=row.management,
                    alternative_medications=row.alternative_medications,
                    source=row.source,
                ))

        highest = None
        if found:
            highest_record = max(found, key=lambda r: _RISK_RANK.get(r.normalized_risk, 0))
            highest = highest_record.normalized_risk

        return InteractionResult(
            pairs_checked=len(pairs),
            interactions_found=found,
            unmatched_drugs=[m for m in unmatched if not m.matched],
            highest_normalized_risk=highest,
        )

    def close(self):
        self._repo.close()
