# Database

## Tables

### `drugs`

| Column | Type | Notes |
|---|---|---|
| `id` | serial / integer PK | |
| `name` | text | Name as it appeared in the source data (DDInter or a clinical note match) |
| `normalized_name` | text, unique | Lowercased, whitespace-collapsed, alias-resolved - used for all lookups |
| `source_identifier` | text, nullable | DDInter's own drug ID, if present in the source file |
| `atc_code` | text, nullable | Reserved for ATC classification data, if/when available in the source |
| `created_at` | timestamp | |

### `drug_interactions`

| Column | Type | Notes |
|---|---|---|
| `id` | serial / integer PK | |
| `drug_a_id` | integer, FK → drugs.id | Always the smaller of the two IDs - see "Canonical pairs" below |
| `drug_b_id` | integer, FK → drugs.id | Always the larger of the two IDs |
| `source_risk` | text | **DDInter's own severity wording, unmodified** |
| `normalized_risk` | text | Our mapped bucket: `major` / `moderate` / `minor` / `unknown` |
| `mechanism` | text, nullable | Interaction description, if present |
| `management` | text, nullable | Management/handling advice, if present in source |
| `alternative_medications` | text, nullable | If present in source |
| `source` | text | `"DDInter 2.0"` for imported records; legacy demo rows are excluded from interaction lookups |
| `created_at` | timestamp | |

Constraints: `drug_a_id < drug_b_id` (canonical ordering, enforced by a
CHECK constraint) and `UNIQUE(drug_a_id, drug_b_id)` (prevents duplicate
rows for the same pair).

## Canonical pairs

"Warfarin + aspirin" and "aspirin + warfarin" describe the same real-world
fact and must resolve to exactly one row. Rather than storing the pair
twice or writing a `WHERE (a=? AND b=?) OR (a=? AND b=?)` query everywhere,
every write and read sorts the two drug IDs first:

```python
a_id, b_id = sorted([id_x, id_y])
```

This means `drug_a_id` in the table has no clinical meaning (it isn't
"the first drug mentioned") - it's simply whichever of the two IDs is
numerically smaller. The application code never needs to check both
orderings; the CHECK constraint guarantees only one ordering can ever be
stored.

## Indexes

- `drugs.normalized_name` - every lookup starts here (see `find_drug_by_normalized_name`)
- `drug_interactions.drug_a_id`, `drug_interactions.drug_b_id` - support the
  foreign key lookups and the pair query

## Example queries

Find a drug by name (used before any interaction check):
```sql
SELECT id, name, normalized_name, source_identifier, atc_code
FROM drugs WHERE normalized_name = 'warfarin';
```

Find the interaction record for a canonically-ordered pair:
```sql
SELECT * FROM drug_interactions
WHERE drug_a_id = 12 AND drug_b_id = 47;
```

## Local vs production

Locally, the same schema (see `backend/database/models.py` -
`SQLITE_SCHEMA` and `POSTGRES_SCHEMA`) runs against a SQLite file at
`data/processed/ddinter/ddinter.db`. In production, it runs against Azure
Database for PostgreSQL. `backend/database/repository.py` is the only file
that branches on which one is active - everything above it is unaware of
the difference.
