# HANDOFF — read this first (current mission supersedes the old build phases)

Written 2026-11-12 from a long planning session with Claude on claude.ai. This file
is the complete context for Claude Code. `CLAUDE.md` describes how the project was
*originally built*; **this file describes what to do now.** Where they conflict, this
file wins.

## 1. Who and why

- Owner: Shirish Giroti (GitHub `dovahkkin1234`), B.Tech CSE (AI major), IIITDM Kancheepuram, 2023-27.
- Goal: polish this repo **today** as the main project artifact for a **Microsoft Research India
  research internship** application (Jan-Jun 2027, Bengaluru, in-office). The role blends HCI, product
  prototyping and applied ML. Named experience areas:
  1. Knowledge graphs (retrieval, entity resolution, graph DBs, GraphRAG)
  2. Agentic memory (episodic/procedural modeling, consolidation, long-term memory)
  3. User understanding / personalization (implicit feedback, proactive experiences, AI-native UX)
  4. LLM evaluation (user studies, behavioral simulation, LLM ablations, personalized benchmarking)
- The application form (forms.cloud.microsoft) was not readable by Claude. The owner relayed one field:
  "Link to your best work — ONE link: something you built that is live and publicly accessible (deployed
  app, website, demo) or a paper you wrote. **Links to GitHub or other code repositories are not accepted.**
  The link must open without a sign-in." The owner will paste the other questions later.

## 1b. PRIORITY CHANGE (added the same evening): the application needs a LIVE LINK, not a repo

Because of that field, the repo is no longer what the reviewer sees. **Task P1 (below) is now the top
priority; it is the artifact that gets judged.** Repo polish still matters (anyone can find the repo) but is
secondary. Order of work now: **P1 -> T0 -> T2 -> T7 -> (only if time: T4b, T3/T4, T5, T6 to feed the page
with real numbers) -> T8 only on request.**

**P1 — Public demo page (static; no backend, no API key, no paid service).**
Goal: a reviewer with 60 seconds on a phone understands what this is, can touch something real, and sees an
honest statement of what is missing. Put it in `site/` as plain HTML/CSS/JS (no build step if avoidable).
Page order:
1. Title, one-line description, and a prominent banner: *"Research prototype (v0). A reworked successor system
   is in progress; this page describes the first version, including what it does not do."*
2. **Live playground (runs entirely in the browser).** Type or pick an error message; the page embeds it
   in-browser with the same model family the project uses (`all-MiniLM-L6-v2`, ONNX build via transformers.js —
   verify the current package name, model ID and CDN URL before coding; lazy-load with a progress indicator
   and a clear fallback message if the load fails). Compare against a small seed memory and show the top-3
   cosine similarities. Then apply the *documented* Triage rule (similarity >= 0.85 and same error_type ->
   known_pattern / L0; 0.70-0.85 -> novel with the match as a hint; otherwise novel) deterministically and
   label it as an illustration: in the real system the LLM applies this rule. Offer the 5 error texts from
   `eval/fixtures/` as "try these". Seed incidents must be labelled as authored examples unless they came from
   a real agent run. **Do not tune seeds or thresholds so that a case "hits"; show what actually happens.**
3. **Save-contract widget.** The user enters confidence and resolution status; the page applies the same
   rules as `src/zeroops/memory/store.py` (reject confidence < 0.5 or `uncertain`; upsert when the normalized
   error signature already exists) and shows the resulting memory state. Port the signature normalization
   from the Python code exactly and note any difference.
4. **How it works:** a small inline-SVG/CSS diagram of Triage -> Investigator (Planner -> Tool -> Evaluator ->
   Hypothesizer -> Verifier) -> Problem Manager -> Reporter, with one sentence on the evaluator's
   `give_up` / `insufficient_evidence` outcome and one on the memory contract.
5. **Evaluation:** include only numbers that come from committed files in `eval/results/` (state provider,
   model, n, runs). If none exist, write a short honest paragraph describing the benchmark *design* (5 seeded
   bugs, cold vs warm memory) and say the page makes no performance claims. No "coming soon" placeholders
   anywhere on the page — ship only what is real.
6. **Limitations / what is missing, stated plainly:** memory is flat embedding retrieval, not a knowledge
   graph; no personalization or user modeling; the benchmark is small, synthetic and authored by the builder;
   this page demonstrates memory retrieval and the save contract, **not** the full LLM agent loop (which needs
   a model backend); no UI for the agent loop in this version.
7. **What's next:** one hedged paragraph (directions, not promises) plus footer with the owner's name/contact
   and a link to the source (fine as a footer link; the *submitted* link is the page itself).
Optional, only if a real run exists: a recorded investigation trace replay, labelled with provider/model.
Hosting: a free static host on a neutral domain (Netlify, Cloudflare Pages or Vercel). Do not use a
`github.io` address for the submitted link (the form rejects GitHub links). Write `docs/DEPLOY.md` with exact
click-by-click steps for the owner (the owner deploys; you never receive credentials).
Acceptance: opens in a private/incognito window with no sign-in; works on a phone; first usable view in
about 10 seconds; no console errors; no keys or secrets in the bundle; no claim the page cannot back up.


## 2. Ground rules (non-negotiable)

1. **No number goes into README, docs, or any application text unless a committed results file in
   `eval/results/` produced it.** Previously circulating numbers ("85%+ ticket deflection", "15x cost
   reduction", "100% pattern accuracy", "54.7s") are **unsubstantiated** — nothing in the repo supports
   them. The "0.85" is only a similarity threshold written in `prompts/triage.md`, not a measured rate.
   There is no token/cost accounting anywhere in the code. Do not reuse those numbers.
2. This audience evaluates LLM systems for a living. Honest scoping beats oversold claims. Sample sizes
   (5 seeded bugs) must be stated plainly. Never claim GraphRAG or personalization unless actually built
   *and* evaluated.
3. **Never read, print, log, or commit `.env` or any API key.** The owner's key lives in `.env`
   (gitignored). Python reads it itself; you never need to. Do not paste keys into prompts or files.
4. **Do not `git push`, and do not touch `main` directly.** Work on branch `polish-msr`, commit in small
   logical steps (the repo has a single "one-shot" commit today; visible iteration is part of the fix).
   The owner pushes.
5. **Zero extra spend.** The owner pays only for a Claude Pro subscription (which covers *interactive*
   Claude Code, not API calls) and will not buy API credit. Do not set or `export ANTHROPIC_API_KEY` in the
   shell that runs Claude Code: Claude Code prefers an API key over the subscription login and would then
   bill the API. Benchmark LLM calls go through a provider chosen in `.env` (see T4b and section 5): a free
   local model is the guaranteed path; Anthropic trial credit is a bonus only if the console actually granted
   some. Print token usage for every run.
6. Ask before destructive actions or any new dependency beyond what is listed here.

## 3. What was verified about the repo (commit 3a288f3, single commit, ~1,968 LOC)

Genuinely good:
- LangGraph graph: Triage -> (known_pattern -> Reporter | else Planner -> Tool Executor -> Evaluator loop
  -> Hypothesizer -> Verifier -> Problem Manager -> Reporter). See `src/zeroops/graph.py`.
- Bounded ReAct loop where `give_up` / `insufficient_evidence` is a first-class designed outcome.
- `src/zeroops/memory/store.py`: SQLite episodic memory with a code-enforced save contract
  (confidence >= 0.5, skip `uncertain`), embedding of normalized error signatures
  (`all-MiniLM-L6-v2`), upsert-on-duplicate-signature (consolidation), cosine top-k retrieval.
  **This is the strongest honest match to the JD's "agentic memory" bullet.**
- `eval/benchmark.py`: 5 seeded bugs in `demo_repo/`; Phase A cold start (bugs 1,2,3,5), Phase B warm
  memory (bug4, a deliberate variant of bug1's `incomplete_symbol_rename` pattern, should hit the L0 path).
  Scores 8 metrics per bug.

Weak links (status as of this handoff):
| # | Weak link | Status |
|---|-----------|--------|
| 1 | `config.py` read `OPENAI_API_KEY`/gpt-4o while docs said Anthropic — repo failed as documented | FIXED in working tree (verify) |
| 2 | `CLAUDE.md` named a different employer's internship | FIXED (genericized) |
| 3 | README was a stub | FIXED (rewritten, results honestly marked pending) |
| 4 | Benchmark never persisted results (console table only; `import json` unused) | **TODO** |
| 5 | No real tests for the `zeroops` package (only `demo_repo/tests/test_auth.py`, which is bug fixture #5) | **TODO** |
| 6 | `server.py` is a 4-line placeholder, no UI | stretch / optional |
| 7 | No graph-structured memory; no personalization | honest limitation; optional stretch |
| 8 | `pyproject.toml` lists `openai>=1.0` though no code imports it | KEEP — needed by the Ollama provider (T4b) |
| 9 | Single commit, no iteration history | fix by committing in small steps from now on |
| 10 | `REPRO_EXECUTION_ENABLED=false` by default — Verifier scaffolded, not exercised | note in README (done); leave off |

## 4. Task list (do in this order; each has an acceptance check)

**T0 — Orient (no code changes).** Read `CLAUDE.md`, this file, `src/zeroops/**`, `eval/benchmark.py`.
Run `git status`, `git diff` to confirm the three working-tree fixes exist. Create branch `polish-msr`
and commit them as separate commits (config fix / CLAUDE.md genericization / README rewrite + this handoff).

**T1 — Environment smoke test.** `uv sync`. Confirm the owner has created `.env` (do not read it; just run).
Run one error end to end:
`uv run python -m zeroops.runner --error-file eval/fixtures/bug1_error.txt`.
If the model ID is rejected, the models in `config.py` defaults may be retired: do NOT silently change
`config.py` defaults; tell the owner and propose `.env` overrides (section 5).
Accept: a Postmortem renders; `incidents.db` is created.

**T2 — Tests that need no API key (highest value-per-hour).** Add `tests/` (pytest) covering:
- `models.py` / `state.py`: a valid sample of every Pydantic model; invalid values rejected (confidence ranges, Literals).
- `memory/store.py`: save contract (raises on confidence < 0.5 and on `uncertain`), upsert on duplicate
  signature (row count stays 1, fields updated), `search_similar` ranks a near-duplicate above an unrelated
  incident, `reset_db`. Use a temp DB path; do not touch the real `incidents.db`.
- `graph.py` routing: `route_from_triage` (known_pattern -> reporter, else planner), `route_from_evaluator`
  (continue/hypothesize/give_up).
- `config.py`: guard test that `pydantic_ai_model` starts with `anthropic:` (prevents the provider-mismatch regression).
- Mock/stub LLM calls; no network. Accept: `uv run pytest -q` green, offline.

**T3 — Persist evaluation results.** Modify `eval/benchmark.py` to write, per run, to
`eval/results/<UTC-timestamp>/`: `results.json` (per-bug metrics + run metadata: git commit hash, model
names from settings, timestamp, loop cap, embed model) and `results.md` (the table). Capture token usage
from PydanticAI run results if available, and compute cost only from **recorded** token counts times
explicitly documented per-token prices stored in the results metadata. Accept: running the benchmark
leaves committed-able files; no hardcoded numbers anywhere.

**T4 — Ablation (maps to the JD's "LLM ablations").** Add a `--no-memory` flag (or env switch) that disables
retrieval for bug4 so we can compare warm-memory L0 routing vs. no-memory investigation on the same bug
(tools called, duration, tokens, correctness). Keep the default behaviour unchanged. Accept: both modes
produce results files with a clearly labelled `condition` field.

**T4b — Provider-agnostic LLM backend (so the benchmark can run for free).** Add `LLM_PROVIDER` to
`config.py`/`.env.example` with values `anthropic` (default, current behaviour) and `ollama`. For `ollama`,
`pydantic_ai_model` / `pydantic_ai_utility_model` must resolve to PydanticAI's Ollama (OpenAI-compatible)
provider at `OLLAMA_BASE_URL` (default `http://localhost:11434/v1`), model names from `LLM_MODEL` /
`UTILITY_MODEL`. Check the installed PydanticAI version's docs/source for the exact class names rather than
guessing. Add offline tests for the provider mapping (extends the T2 config guard test). Document in README
how a reviewer can reproduce the benchmark for free with Ollama. Optional, only if the owner asks: a
`claude-cli` backend that shells out to `claude -p` (counts against Pro's separate monthly Agent SDK credit,
not API billing; verify flags with `claude --help`; label results with the backend since the CLI wraps the
model in Claude Code's own prompt/tooling, which makes it a less clean measurement). Never extract or reuse
the subscription OAuth token directly — that is prohibited; only invoke the official CLI.
Accept: switching `LLM_PROVIDER` changes nothing else; default behaviour unchanged; tests green offline.

**T5 — Real runs (owner runs these on the Windows host, which has the GPU; the VM does not).** Prepare
exact commands and a one-page runbook (`docs/RUNBOOK.md`) for: installing Ollama, pulling a tool-calling-capable
7-8B instruct model, setting `.env` (`LLM_PROVIDER=ollama`, model names), and running the benchmark and
ablation. First do a one-off check that the chosen local model can satisfy the PydanticAI structured outputs
(Triage/Evaluator decisions); if validation failures are frequent, say so rather than hiding them — retry
counts and failure rates are themselves results. Run each condition **3 times** and report per-run results plus
the spread; with n=5 bugs report counts like "4/5" with the sample size beside them, never bare percentages.
If the owner also has Anthropic trial credit or chooses the `claude-cli` backend, run the same benchmark with
Claude too and report it as a labelled second model (model comparison). Results are committed by the owner
from the host and pulled into the VM for T6. Accept: every figure in the README links to a file in
`eval/results/`, and each results file states provider, model, and backend.

**T6 — README evaluation section.** Replace "results pending" with a table generated from the committed
results (or generate it with a small script so numbers cannot drift). State: models used, n, number of
runs, cost incurred, and the limitations (small synthetic benchmark, seeded bugs authored by the same
person who built the agent, self-reported confidence not externally calibrated). Keep the existing
Limitations section; update it if anything changed.

**T7 — Housekeeping.** **Keep the `openai` dependency** in `pyproject.toml` — PydanticAI's Ollama
(OpenAI-compatible) provider needs the OpenAI client (no code imports it directly). Delete the leftover
`server.py` claim in docs if a UI is not built, make sure `.env.example` matches `config.py` (including the
new `LLM_PROVIDER` / `OLLAMA_BASE_URL`).

**T8 — Stretch (only if T0-T7 are done and time remains; time-box to ~2 hours; stop and ask before starting).**
Option A (best JD fit): lightweight graph-structured memory — a `networkx` graph linking
incident <-> affected file <-> root-cause pattern <-> commit, used by the Problem Manager and Triage to
retrieve *related* incidents beyond embedding similarity; evaluate it against flat retrieval on the existing
benchmark and report honestly, including if it does not help. Option B: minimal FastAPI + SSE streaming UI
for the investigation trace (HCI/product-prototyping signal). Do not claim either until built, tested,
and evaluated.

## 5. Models and cost

- `config.py` defaults: `claude-opus-4-7` (reasoning) and `claude-haiku-4-5-20251001` (utility). These IDs
  date from April 2026 and may no longer be served. Do not guess; if a call fails with a model-not-found
  error, propose `.env` overrides, e.g. `LLM_MODEL=claude-sonnet-5-5` and `UTILITY_MODEL=claude-haiku-5-5`
  (current IDs as of Nov 2026 — verify with a one-line call before relying on them). Record whichever models
  were actually used in every results file.
- Prefer the cheapest model that works for benchmark runs; mention the choice in the README.

## 6. Security posture of this session

The owner wants least-privilege. `.claude/settings.json` in this repo denies reading `.env`, `git push`,
network fetch tools, and destructive commands. Deny rules are a speed bump, not a wall (a determined shell
one-liner could still read a file), so do not attempt to read `.env` by any route, and treat the trial key's
spend cap as the real safety net. If a task seems to require reading the key, stop and tell the owner.

## 7. Definition of done for today

- [ ] **P1 page built in `site/`, deployed by the owner, URL verified in a private window and on a phone**
- [ ] Branch `polish-msr` with a readable commit history (not one blob)
- [ ] `uv run pytest -q` green offline
- [ ] `LLM_PROVIDER` switch (anthropic | ollama) implemented, tested, documented; `docs/RUNBOOK.md` written
- [ ] Benchmark + ablation results committed under `eval/results/` with metadata (provider, model, backend)
- [ ] README Evaluation section generated from those files; every number traceable
- [ ] README Limitations section accurate (no GraphRAG / personalization / UI unless built)
- [ ] Owner has a short summary of what changed and anything that failed
Then stop. The owner reviews the diff and pushes.
