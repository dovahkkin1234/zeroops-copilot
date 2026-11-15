# ZeroOps Copilot — Evaluation Runbook

This is the step-by-step guide for running the benchmark on the Windows host
(the machine with the GPU and local Ollama). Claude Code never executes these;
the owner runs them in PowerShell.

---

## 0. Prerequisites

Assumed already installed:
- Python 3.11+ with `uv` (`pip install uv`)
- Git

Check:
```powershell
python --version   # must be 3.11+
uv --version
git --version
```

Install project dependencies (once):
```powershell
cd C:\Users\shiri\Projects\zeroops-copilot
uv sync
```

---

## 1. Ollama setup

### 1a. Install Ollama
Download from https://ollama.com/download (Windows installer).
After install, verify:
```powershell
ollama --version
```

### 1b. Pull a tool-calling model

**Recommended:** `qwen2.5:7b` — good structured-output reliability, 4.7 GB.
```powershell
ollama pull qwen2.5:7b
```

**Alternative if 7B is too slow:** `qwen2.5:3b` (~2 GB, faster but less reliable):
```powershell
ollama pull qwen2.5:3b
```

**Verify Ollama is running and the model responds:**
```powershell
ollama run qwen2.5:7b "Return JSON: {\"ok\": true}"
```
Expected: some JSON response.

### 1c. Configure `.env`

Edit `.env` (copy from `.env.example` if it doesn't exist):
```
LLM_PROVIDER=ollama
LLM_MODEL=qwen2.5:7b
UTILITY_MODEL=qwen2.5:7b
OLLAMA_BASE_URL=http://localhost:11434/v1
EMBED_MODEL=all-MiniLM-L6-v2
DB_PATH=./incidents.db
REPO_PATH=./demo_repo
MAX_INVESTIGATION_LOOPS=8
REPRO_EXECUTION_ENABLED=false
# ANTHROPIC_API_KEY=  # leave commented out to avoid API billing
```

> **Important:** Do NOT set `ANTHROPIC_API_KEY` while running Ollama. Claude Code
> prefers an API key over the subscription login and would bill your API account.

---

## 2. Smoke test — one bug end-to-end

Before running the full benchmark:
```powershell
uv run python -m zeroops.runner --error-file eval/fixtures/bug1_error.txt
```

Expected: a postmortem renders with `hypothesis.pattern = incomplete_symbol_rename`.
If you see `model not found`, verify `LLM_MODEL` in `.env` matches the pulled model name.

---

## 3. Main benchmark (5 seeded bugs)

### 3a. With-memory run (default)
```powershell
uv run python -m eval.benchmark
```

Runs Phase A (bugs 1, 2, 3, 5 against empty memory) then Phase B (bug4 — should
hit the L0 fast-path if bug1 was resolved and saved). Takes ~30-60 min with a 7B model.

Results saved to `eval/results/<timestamp>/results.json` and `results.md`.

### 3b. Ablation — no-memory run
```powershell
uv run python -m eval.benchmark --no-memory
```

Clears memory before Phase B so bug4 must be investigated from scratch.
Compare against 3a: more tools called, longer duration, L0 path not taken.

### 3c. Run 3 times each for spread
Run 3a and 3b at least 3 times each with the same model. Record the timestamp
for each run. Report as "X/5 (n=3)" not bare percentages.

---

## 4. BugsInPy evaluation (real-world bugs)

### 4a. Download metadata (no LLM, no git clones)
```powershell
uv run python -m eval.bugsinpy_eval --setup
```

Downloads bug.info files for `tqdm`, `luigi`, `black`, `httpie`, `thefuck` from
the BugsInPy GitHub repository. Saves to `eval/bugsinpy_data/metadata.json`.
Takes ~2 min; uses ~50 GitHub API calls (unauthenticated limit: 60/h).

If you hit the rate limit, set a free GitHub personal access token:
```powershell
$env:GITHUB_TOKEN = "ghp_your_token_here"
uv run python -m eval.bugsinpy_eval --setup
```

### 4b. Collect error traces (no LLM, needs git + pip)
```powershell
uv run python -m eval.bugsinpy_eval --collect
```

For each bug in the metadata:
- Clones the project repository into `eval/bugsinpy_data/repos/<project>/`
- Checks out the buggy commit
- Runs `pip install -e .` and the failing test
- Captures the error trace and ground-truth diff

Takes ~20-40 min depending on network speed (clones ~5 repos, ~50-500 MB total).
The repos are gitignored and not committed.

Dry-run first to preview what will be collected:
```powershell
uv run python -m eval.bugsinpy_eval --collect --dry-run
```

### 4c. Run agent on collected traces (needs LLM + Ollama)
```powershell
uv run python -m eval.bugsinpy_eval --run
```

Runs the ZeroOps agent on each captured error trace. Grades fault localization:
"did the agent's evidence include at least one of the files changed in the fix?"

Results saved to `eval/results/<timestamp>/bugsinpy_eval.json`.

---

## 5. SO duplicate retrieval eval (no LLM, offline after first run)

```powershell
uv run python -m eval.so_eval --n-pairs 300
```

Already run once; results in `eval/results/20261115T210854Z/so_eval.json`.
Re-run uses the cached pairs instantly. Useful if you want to verify on a
different machine or after a code change.

---

## 6. Committing results

After each evaluation run, commit the results files (not the repos or raw data):
```powershell
git add eval/results/
git commit -m "eval: add <model> benchmark/ablation results"
```

Do NOT commit:
- `eval/bugsinpy_data/repos/` (gitignored — large git repos)
- `eval/bugsinpy_data/traces/` (gitignored — derived data)
- `eval/so_data/` (gitignored — raw SO data)
- `.env` (gitignored — API keys)

---

## 7. Updating the README

After committing results, update `README.md → Evaluation` section.
The numbers that go into the README must come from committed files in `eval/results/`.
No unsubstantiated numbers, ever.

For BugsInPy, report as:
- `X/Y bugs (n_runs=3, model=qwen2.5:7b, provider=ollama)` — not bare percentages
- State: "bugs authored by third parties; ground truth is the fix commit diff"

---

## 8. Troubleshooting

| Symptom | Likely cause | Fix |
|---------|-------------|-----|
| `model not found` | Model name mismatch | Run `ollama list` and match LLM_MODEL exactly |
| `connection refused` | Ollama not running | Run `ollama serve` in a separate terminal |
| `PydanticAI validation failed` | Model didn't return valid JSON | Retry; switch to a larger model (14B) if persistent |
| Benchmark hangs | Ollama overloaded | Check GPU memory; reduce `MAX_INVESTIGATION_LOOPS` to 4 |
| Bug collect fails | Python version mismatch | Some BugsInPy bugs need Python 3.6-3.8; skip them and use the ones that work |
| GitHub rate limit | Too many API calls | Set `GITHUB_TOKEN` env var |
