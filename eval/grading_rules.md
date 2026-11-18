# Benchmark Grading Rules

## Rule G1 — Uniform pattern grading across all resolution paths

**Applies to:** all bugs, all conditions (with_memory, no_memory).

For every bug, `pattern_correct` is determined by comparing the
**retrieved or generated pattern** against `BUGS[bug_id]["expected_pattern"]`:

- **Investigated path** (`resolution_status = "resolved"`):
  use `state["hypothesis"]["pattern"]`
- **L0 fast path** (`resolution_status = "known_pattern"`):
  use `state["triage"]["matched_pattern"]` (the `root_cause_pattern` of the
  retrieved past incident, stored by the triage node at match time)
- **Give-up path** (`resolution_status = "uncertain"`):
  `pattern_correct = False` (no pattern was produced)

Same rule, same field semantics, same comparison — no special casing for L0.

## Rule G2 — Uniform file grading across all resolution paths

Analogous to G1. For L0 hits, `file_found` is True if any file in
`state["triage"]["matched_files"]` matches `BUGS[bug_id]["expected_file"]`.
For investigated paths, `file_found` checks `state["evidence"]` as before.

## Motivation

Before this rule was committed (runs up to and including 20261116T160526Z),
L0 hits always scored `pattern_correct = False` and `file_found = False`
because the grader checked `hypothesis` and `evidence` — both of which are
empty on the L0 path.  The result was:

- bug4 (all 3 with_memory runs): graded ❌/❌ even when the retrieved
  pattern was correct.
- bug7 (all 3 with_memory runs): graded ❌/❌ — AND the retrieved pattern
  appears to have been incorrect (see note below).

## Known false positive — bug7

bug7 (`AttributeError: module 'collections' has no attribute 'Mapping'`)
hit the L0 fast path in every with_memory run (0 tools, confidence ≈ 51%).
The expected pattern is `stale_import`.

bug5 (`ImportError`) is not a likely candidate: the triage prompt asks the LLM
to prefer same-error-type matches, but this is LLM guidance and not enforced in
code, so bug5 is not guaranteed to be excluded.  The most likely match is bug1
(`AttributeError: module 'auth' has no attribute 'validate_token'`), whose
template is structurally identical to bug7's error text; bug1's
`root_cause_pattern` is `incomplete_symbol_rename`.

If confirmed by re-run: bug7's L0 retrieval is a **wrong-pattern false positive**
(`incomplete_symbol_rename` returned, `stale_import` expected).  This is documented
plainly in the README Limitations section and in CLAIMS.md.

## Implementation

The pipeline fix is in:
- `src/zeroops/agents/triage.py`: triage node stores `matched_pattern` and
  `matched_files` in the triage dict on L0 hits.
- `eval/benchmark.py` → `_score_result()`: uses these fields for L0 grading.

Old results in `eval/results/` are **not modified**.  The first run with the new
grader produces a new directory and is compared side-by-side with the old numbers.
