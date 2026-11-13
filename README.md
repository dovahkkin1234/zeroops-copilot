# ZeroOps Copilot

A multi-agent prototype that shifts incident tickets leftward — from L3
investigation to L0 auto-resolution to prevented — aligned with the
industry's ZeroOps direction.

**Built by:** Shirish Giroti · [GitHub](https://github.com/dovahkkin1234) · IIITDM Kancheepuram · April 2026

## 30-second pitch

IT tickets are one of the largest operational cost centers in enterprise
engineering. The industry is shifting to **ZeroOps** — a target state of
zero operational tickets — by pushing tickets leftward down the support
tiers (L3 → L2 → L1 → L0 → prevented). This project is a working
prototype of that architecture: three coordinated agents that triage,
investigate, and prevent recurrence of production incidents in a Python
codebase.

## Architecture

Three agents on one [LangGraph](https://github.com/langchain-ai/langgraph) state
machine, sharing one `AgentState`, one tool catalog, and one SQLite-backed
memory store:

- **Triage Agent** — runs semantic similarity search against learned
  incident memory. If the top match clears a similarity threshold (0.85)
  with a matching error type, the ticket is auto-resolved from memory
  (L0 path). Otherwise it's routed to the Investigator, with any
  below-threshold match attached as a hint.
- **Investigator Agent** — a bounded ReAct loop: Planner decides the next
  tool call, Tool Executor runs it, and a dedicated Evaluator node
  decides after every step whether to `continue`, `hypothesize`, or
  `give_up`. `give_up` (surfaced as `insufficient_evidence`) is a
  first-class, designed outcome — the loop is capped at
  `MAX_INVESTIGATION_LOOPS` and will say "I don't know, here's what I
  tried" rather than force a confident wrong answer. Once a hypothesis
  forms, a Verifier node generates a minimal reproduction script
  (execution is gated behind `REPRO_EXECUTION_ENABLED`, off by default).
- **Problem Manager Agent** — takes the resolved hypothesis's root-cause
  pattern and scans the codebase for other places the same pattern
  exists, producing Prevention Tickets for verified matches.

## The agentic core: the evaluator loop

This is the part of the project I'd point a reviewer at first. After
every tool call, the Evaluator decides `continue` / `hypothesize` /
`give_up` based on accumulated evidence — not a fixed number of steps.
Treating "insufficient evidence" as a valid terminal state, rather than
something to paper over, is a deliberate design choice: a system that
can admit uncertainty is more trustworthy than one that always produces
an answer.

## Incident memory

`src/zeroops/memory/store.py` implements a confidence-gated,
upsert-based memory: an incident is only persisted if resolution
confidence ≥ 0.5 and the resolution status isn't `uncertain`; a repeat
of the same error signature updates the existing record instead of
duplicating it. Retrieval is cosine similarity over
`sentence-transformers` (`all-MiniLM-L6-v2`) embeddings of normalized
error signatures, top-k via `search_similar`. This is the project's most
genuinely reusable piece of agentic-systems engineering — confidence
gating and consolidation on write, semantic retrieval on read.

## Built with

- **Claude Opus 4.7** (reasoning nodes) and **Claude Haiku 4.5**
  (non-reasoning formatting) via PydanticAI, for strict structured
  outputs on every agent node
- **Claude Code**, inside the **Antigravity** IDE, as the primary
  development agent — roughly 70% of the code was scaffolded from
  scoped prompts and then reviewed/corrected by hand; the architecture,
  prompt designs, and integration logic were human-driven
- **LangGraph** for state-machine orchestration
- **sentence-transformers** (`all-MiniLM-L6-v2`) for local, dependency-free
  incident similarity
- **SQLite** for incident memory
- **`rich`** for the CLI; a FastAPI + Next.js streaming web UI was
  scoped but not built (see Limitations)

## Quickstart

```bash
uv sync
cp .env.example .env  # fill in ANTHROPIC_API_KEY
uv run python -m zeroops.runner --error-file eval/fixtures/bug1_error.txt
```

For the benchmark:

```bash
uv run python -m eval.benchmark
```

## Demo scenarios

The repo ships with `demo_repo/` — a toy Python app with 5 seeded bugs.
Bug 4 is a deliberate variant of bug 1's pattern
(`incomplete_symbol_rename`), used specifically to exercise the Triage
L0 fast path once memory has been warmed by an earlier run.

## Evaluation

`eval/benchmark.py` runs all 5 seeded bugs in two phases — cold-start
(bugs 1, 2, 3, 5 against empty memory) and warm-memory (bug 4, which
should hit the L0 path) — and scores 8 metrics per bug (triage
correctness, pattern correctness, file-localization correctness,
self-reported confidence, resolution status, tool-call count,
duration, prevention-ticket count). Results are persisted to
`eval/results/<timestamp>/` as `results.json` and `results.md`.

**Run `20261113T113725Z` — full results committed to this repo.**

| Metric | Result | Notes |
|---|---|---|
| Pattern accuracy | 4/5 | bug5 (`stale_import`) misidentified |
| File localization | 2/5 | bugs 2 and 4 found the pattern but not the specific file |
| Average confidence | 86% | model self-reported; not externally calibrated |
| L0 routing (bug4) | miss | bug1 confidence=30% fell below the 0.5 save threshold, so it was never written to memory — **this is the save contract working correctly**, not a routing bug |
| Prevention tickets | 5 total | 1.0 per completed bug on average |
| Total duration | 643.5s | ~10.7 min for 5 bugs end-to-end |

Provider: `google-gla` (Gemini). Due to the free-tier 20 req/day cap per
model, each bug ran on a separate Flash/Flash-Lite model (see
`results.json` → `metadata.per_bug_models` for the per-bug breakdown).
This is a single-condition run; a multi-model ablation with consistent
model assignment across bugs would require billing enabled or a local
model (see `docs/RUNBOOK.md` for Ollama instructions).

**Limitations of this evaluation:**

- n=5 bugs, synthetic, authored by the same person who built the agent —
  not an independent evaluation
- Each bug ran on a different model; not a clean single-model measurement
- Confidence values are model self-reported; no ground-truth calibration
- The benchmark does not cover distributed traces, async/timing bugs,
  or any pattern outside the five seeded cases

## Ticket taxonomy reference

For reviewers unfamiliar with AMS vocabulary:

- **L0**: self-service, no human touch
- **L1**: first-line, scripted troubleshooting
- **L2**: functional and technical analysis
- **L3**: developer-level deep-dive
- Each tier escalation roughly doubles cost; the economic game is
  shift-left.

## Limitations (honest scope boundaries)

- **No knowledge graph / GraphRAG.** Incident memory is flat rows +
  vector similarity, not an entity graph — there's no modeling of
  relationships *between* incidents, files, or root causes beyond
  independent embeddings. A graph-structured memory (incidents ↔ files
  ↔ commits ↔ root-cause patterns) is the most obvious next step and
  isn't built yet.
- **No personalization layer.** The system treats every incoming error
  identically; there's no per-user or per-team modeling, no implicit
  feedback loop, no notion of a user's history shaping how results are
  presented.
- **Small synthetic benchmark.** One run of 5 seeded bugs is committed
  to `eval/results/`; the bugs were authored by the builder and are not
  an independent evaluation. See the Evaluation section for the full
  caveats.
- **No web UI.** `server.py` is a placeholder; the CLI is the only
  interface.
- **Test suite covers only the offline layer.** `tests/` has 67 pytest
  tests for models, state, memory (save contract, upsert, search), graph
  routing, and config — all offline and without an API key. End-to-end
  agent tests require a model backend and are not included.
- Python only, single-service, synchronous stack traces. Out of scope:
  distributed traces, async/timing bugs, data-layer issues,
  infrastructure failures.
- Repro execution is sandboxed via subprocess only, and off by default
  (`REPRO_EXECUTION_ENABLED=false`); a proper container-based sandbox
  is a next step.
- Incident memory is local SQLite; a real deployment would need a
  shared vector DB or graph store.

## What this unlocks next

The three-agent pattern generalizes to the fuller AMS taxonomy — Service
Requests, Change Management, Event Management — and the memory layer is
the natural place to grow: toward a proper entity graph over incidents,
files, and root-cause patterns (closing the GraphRAG gap above), and
toward per-team retrieval that accounts for who's asking, not just what
they're asking.
