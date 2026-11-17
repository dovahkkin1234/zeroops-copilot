# ZeroOps Copilot — current-state Claude Code context

> The original build brief (architecture decisions, node prompts, demo-bug
> patterns, hour-by-hour plan) is in `docs/ORIGINAL_BUILD_BRIEF.md`.
> This file describes the **current state** of the repo for ongoing work.

## Branch and state

- Active branch: `polish-msr` (all real work; `main` tracks it)
- Python 3.11+, package manager: `uv`
- LLM calls: `src/zeroops/agents/_llm.py` → `run_as_json()` / `run_as_json_list()`
  (plain-text output + JSON extraction + Pydantic validation; PydanticAI
  structured-output/tool-calling mode is **not** used)
- All committed benchmark runs: `qwen2.5:7b` via Ollama, `LLM_PROVIDER=ollama`
- Anthropic provider path exists in config but has never been run end-to-end (no key)

## Repo structure (key paths)

```
src/zeroops/
  agents/          triage, investigator (planner/tool/evaluator/hyp/verifier),
                   problem_manager, reporter, _llm.py
  memory/          store.py (SQLite + embeddings), graph_store.py (networkx)
  tools/           code.py, git.py, repro.py, memory.py
  prompts/         one .md file per agent node
  config.py        Settings (pydantic-settings); LLM_PROVIDER switch
  graph.py         LangGraph StateGraph assembly
  runner.py        CLI entry point (rich)
eval/
  benchmark.py     7-bug benchmark, Phase A cold + Phase B warm-memory
  so_eval.py       Stack Overflow duplicate retrieval eval (n=124)
  fixtures/        7 error .txt files
  results/         committed run outputs
tests/             80 offline pytest tests (no model backend needed)
site/              static demo page (index.html)
docs/              DEPLOY.md, RUNBOOK.md, CLAIMS.md, ORIGINAL_BUILD_BRIEF.md
```

## Hard constraints (non-negotiable)

1. Never read, print, or commit `.env` or any API key.
2. Never run `git push`, `git merge`, or `git remote` — the owner does that.
3. All numbers in README/docs/resume must trace to a committed file in `eval/results/`.
4. Do not soften any caveat, limitation, or weakness.
5. Commit style: `feat:/fix:/docs:/results:` prefix; no Co-Authored-By trailer.
6. Keep the "~70% scaffolded with Claude Code" disclosure.

## Known gaps (document, do not hide)

- `run_as_json_list()` returns `[]` silently after a failed retry (prevention tickets).
- Anthropic provider never validated end-to-end.
- Graph memory is 1-hop traversal only; not GraphRAG.
- Repro execution is off by default (`REPRO_EXECUTION_ENABLED=false`).
- No web UI (`server.py` is a placeholder).

## docs/ file status

| File | Status |
|---|---|
| `ORIGINAL_BUILD_BRIEF.md` | Original April 2026 build brief; historical reference |
| `HANDOFF.md` | Internal session handoff (MSR application, Nov 2026); stale as project context |
| `DEPLOY.md` | Current — Netlify Drop steps for `site/` |
| `RUNBOOK.md` | Current — Ollama setup and benchmark reproduction |
| `CLAIMS.md` | Current — resume-claim evidence map |
| `ams_glossary.md` | Reference glossary; not stale |
