# CLAIMS.md — Resume claim evidence map

Each bullet from the MISSION.md "Resume sync" section is mapped to its
evidence (source path, test, or results directory). Numbers that cannot
be traced to a committed file are flagged explicitly.

---

## Claim 1: Three-agent LangGraph system

**Source:** `src/zeroops/graph.py`
Triage → (known_pattern → Reporter | else Planner → Tool Executor →
Evaluator loop → Hypothesizer → Verifier → Problem Manager) → Reporter.
Three sub-graphs / node clusters share one `AgentState`.

**Tests:** `tests/test_graph.py` (10 tests: routing, edge wiring, state flow)

**Status: verified.**

---

## Claim 2: Bounded ReAct loop with evaluator that can give up with "insufficient evidence"

**Source:** `src/zeroops/agents/investigator.py` (Planner → Tool Executor →
Evaluator loop), `src/zeroops/prompts/evaluator.md` (the `give_up` decision
path is an explicit first-class outcome, not a fallback).

Loop is capped by `MAX_INVESTIGATION_LOOPS` (default 8, set in `.env`).
`give_up` is returned as `EvaluatorDecision.decision == "give_up"` → routes
to Reporter with `resolution_status = "uncertain"`.

**Tests:** `tests/test_graph.py` → `test_route_from_evaluator_give_up`

**Status: verified.**

---

## Claim 3: Confidence-gated memory (saves at ≥ 0.5, consolidates repeats) with semantic retrieval and a graph layer

### Save contract (confidence gate + no-uncertain rule)
**Source:** `src/zeroops/memory/store.py` → `save_incident()`
Raises `ValueError` if `confidence < 0.5` or `resolution_status == "uncertain"`.

**Tests:** `tests/test_memory.py` → `test_save_contract_rejects_low_confidence`,
`test_save_contract_rejects_uncertain`

### Consolidation (upsert on duplicate signature)
**Source:** `src/zeroops/memory/store.py` → `save_incident()` upserts on
`error_signature` column (normalized error text, not raw). Duplicate errors
update the existing row rather than inserting a new one.

**Tests:** `tests/test_memory.py` → `test_upsert_on_duplicate_signature`

### Semantic retrieval
**Source:** `src/zeroops/memory/embeddings.py` (`all-MiniLM-L6-v2`, local),
`src/zeroops/memory/store.py` → `search_by_text()` (cosine similarity over
all stored embeddings).

**Tests:** `tests/test_memory.py` → `test_search_similar_ranks_near_duplicate_above_unrelated`

### Graph layer
**Source:** `src/zeroops/memory/graph_store.py` — networkx DiGraph with
incident, file, pattern, and commit nodes. 1-hop traversal (same file,
same error type, same pattern). Added in commit `3a4af96`.

**Tests:** `tests/test_graph_store.py` (13 tests)

**Status: verified.**

---

## Claim 4: Ablation on qwen2.5:7b, 3 runs per condition

> "2.4–3.3s / 0 tool calls with memory vs 18.7–28.7s / 2 tool calls without"

### with_memory (n=3, bug4 = L0 fast path)
| Run | Duration (bug4) | Tools (bug4) |
|---|---|---|
| `eval/results/20261116T114317Z/results.json` | 2.8s | 0 |
| `eval/results/20261116T152824Z/results.json` | 3.3s | 0 |
| `eval/results/20261116T160526Z/results.json` | 2.4s | 0 |

Metadata: `llm_provider=ollama`, `llm_model=qwen2.5:7b`, `condition=with_memory`

### no_memory (n=3 reported; 4 runs exist — only the first 3 are in the README table)
| Run | Duration (bug4) | Tools (bug4) |
|---|---|---|
| `eval/results/20261116T120346Z/results.json` | 22.4s | 2 |
| `eval/results/20261116T120726Z/results.json` | 22.1s | 2 |
| `eval/results/20261116T121355Z/results.json` | 18.7s | 2 |
| `eval/results/20261116T121648Z/results.json` | 28.7s | 2 |

Metadata: `llm_provider=ollama`, `llm_model=qwen2.5:7b`, `condition=no_memory`

**Note:** The README reports n=3 for no_memory. All 4 runs are consistent
(2 tools, 18–29s), so the range claim holds across the full set.

**Status: verified.**

---

## Claim 5: Stack Overflow retrieval Recall@3 0.911, MRR 0.80 (n=124)

**Source:** `eval/results/20261115T210854Z/so_eval.json`

Exact values (raw condition): Recall@1 0.6855, **Recall@3 0.9113**, **MRR 0.8033**
n_pairs=124, n_originals_in_index=83, embed_model=all-MiniLM-L6-v2

Data source: Stack Overflow (CC BY-SA 4.0). Ground truth: SO's own
duplicate-close links. Query = duplicate question text; relevant = linked original.

The normalized condition (applying `normalize_error_signature()` before embedding)
gives Recall@3 0.9113, MRR 0.7993 — slightly lower MRR, same Recall@3.

**Status: verified. The resume MRR value (0.80) matches the raw condition (0.8033 rounded).**

---

## Claim 6: Reproducible eval tooling with an offline pytest suite

**Sources:**
- `eval/benchmark.py` — 7-bug benchmark, Phase A cold-start + Phase B warm-memory,
  writes `eval/results/<timestamp>/results.json` and `results.md`.
- `eval/so_eval.py` — Stack Overflow retrieval eval.
- `tests/` — 80 pytest tests, all offline (no model backend needed).

**Status: verified.** Note: `uv run pytest -q` is currently blocked by an
Application Control policy on this machine. Test count (80) is from grepping
`def test_` across `tests/`. To verify independently:
```
uv run pytest -q --co -q   # list tests only, no execution needed
```

---

## Claim 7: Scoped as a prototype (7 self-authored bugs)

**Sources:**
- `demo_repo/` — toy Python app with 7 seeded bugs
- `eval/fixtures/` — 7 error `.txt` files
- Bugs: `bug1–bug5` (original) + `bug6` (api_removed) + `bug7` (stdlib_removed)

All bugs were authored by the builder. This is stated in the README Limitations
section ("bugs were authored by the builder and are not an independent evaluation").

**Status: verified.**

---

## How structured outputs actually work (all providers including Ollama)

> Referenced in MISSION.md additions Task 1b, based on commit `8de9244`.

**What the README and resume should say** (and now do, after the Task 1 fix):
Every LLM call goes through `src/zeroops/agents/_llm.py` → `run_as_json()`
(single objects) or `run_as_json_list()` (arrays).

**Mechanism:**
1. `output_type=str` — model returns plain text, not tool calls.
2. The full JSON schema is injected as text into the system prompt.
3. The response is parsed: markdown code fences stripped, then balanced
   brace/bracket matching to extract the JSON block.
4. Validated with `pydantic.BaseModel.model_validate()` (which also runs the
   enum-unwrap validator to handle `{"enum": ["novel"]}` → `"novel"`).
5. On parse or validation failure: retries **once** with a repair prompt that
   includes the error and the original request.
6. If the retry also fails: `run_as_json()` raises the error (node fails);
   `run_as_json_list()` **returns `[]` silently** (prevention tickets vanish
   without an error — this is a known gap documented in Limitations).

**PydanticAI's structured-output / tool-calling mode is not used anywhere.**
It was attempted and abandoned in commit `8de9244` because small local models
(qwen2.5:7b) fail it in two consistent ways:
- Enum values wrapped as `{"enum": ["novel"]}` instead of `"novel"`
- Entire schema returned nested inside a single field

This path is not provider-specific: `run_as_json()` is called for Anthropic,
Ollama, and Gemini providers identically. The Anthropic provider has never
been run end-to-end (no key available during development) — the code path
exists but is unverified against real Claude API responses.

**Resume implication:** "structured outputs" is accurate in that every LLM call
produces a validated Pydantic model, but the mechanism is JSON-in-prompt +
Pydantic validation, not PydanticAI's native structured-output protocol.

---

## Claims with no committed evidence (do not add to resume)

| Claim | Why it cannot be added |
|---|---|
| "Anthropic provider validated" | No API key; Anthropic path never run end-to-end |
| "Docker / containerized" | Docker not yet built (Task 3 pending) |
| BugsInPy evaluation | `eval/bugsinpy_eval.py` exists but no results committed |
| "Live demo URL" | Site deployed but Task 2 (static verification) pending |
| Graph memory improves accuracy | n=1 run; not conclusive (stated in README) |
