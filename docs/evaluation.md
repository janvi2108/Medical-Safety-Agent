# Evaluation

## Why evaluate at all

A pipeline that "seems to work" on a couple of manual tries isn't the same
as one whose accuracy has actually been measured. This document describes
how to build and run a small evaluation set against the pipeline, and what
to report from it.

## Building the evaluation set

Create 10-30 synthetic clinical notes (extend `data/sample_notes/` or
build a separate `data/eval_notes/` folder) covering:

- Single medication
- Multiple medications, no interaction
- Multiple medications, one known interaction
- Multiple medications, more than one interaction
- Messy/informal clinical language
- Missing dosage information
- Duplicate medication mentions
- At least one medication unlikely to be in DDInter (to test the
  "unmatched drug" path)

For each note, record ground truth by hand:
- The medications a human would extract
- Which pairs (if any) have a documented DDInter interaction

## Metrics to compute

**Extraction (Agent 1):**
- **Precision** = correctly extracted medications / total medications extracted
- **Recall** = correctly extracted medications / total medications actually present
- **F1** = harmonic mean of precision and recall

**Interaction retrieval (Agent 2 + database):**
- **Retrieval accuracy** = correctly identified interaction pairs / total pairs with a known ground-truth interaction
- **False positives** = pairs flagged as interacting that shouldn't have been (should be near-zero, since this stage is a deterministic lookup, not a guess - a false positive here would indicate a bug, e.g. a normalization or canonical-ordering error, not model unpredictability)
- **False negatives** = known interactions that were missed (usually indicates either a data-loading gap or a name-matching failure - check the `unmatched_drugs` field first)

**Safety rules:**
- Since `services/safety_rules.py` is pure deterministic logic, its
  correctness is fully covered by `tests/test_safety_rules.py` (exhaustive
  unit tests) rather than a statistical evaluation - there's no
  "accuracy percentage" to compute for deterministic if/else logic.

**Patient communication (Agent 3) - qualitative:**
- Does the explanation ever state a fact not present in the verified
  findings it was given? (Manually inspect a sample - this is the one
  place a subtle LLM error could slip past automated checks.)
- Does it ever use disallowed language (dosing instructions, "these
  medications are safe," a diagnosis)?
- Is it readable by someone without a medical background?

**Latency:**
- Average and p95 response time per pipeline stage (extraction call,
  database lookup, summary call) - `backend/main.py` can be extended to
  log per-stage timing if you want to track this over time.

## Documenting limitations

Whatever numbers come out of this evaluation, report them alongside their
limits:
- Sample size (10-30 notes is enough to catch obvious bugs, not enough to
  make a statistically rigorous accuracy claim)
- The synthetic notes are written by the same person who built the
  pipeline, which can introduce bias toward phrasing the system already
  handles well
- This is an educational prototype evaluation, not a clinical validation
  study, and should never be represented as one

## Running an evaluation pass

There is no automated eval script bundled by default (to keep the
project from overengineering something you may want to customize) - the
recommended approach is a short Python script that:

1. Loops over your evaluation notes
2. Calls `backend.agents.orchestrator.run_pipeline()` for each
3. Compares `medications` and `interactions.interactions_found` against
   your hand-recorded ground truth
4. Prints a summary table, similar in spirit to the ingestion summary
   printed by `scripts/load_ddinter.py`

This is intentionally left as a next step rather than pre-built, since a
good evaluation set is specific to the notes you actually write - see
`tests/test_interactions.py` for the pattern of seeding a temporary
database and asserting on results, which the eval script can reuse.
