# Runbook — running the benchmark for free with Ollama

This guide lets you reproduce the benchmark on your own machine without
spending Anthropic API credit. It requires a GPU (or fast CPU — slower
but functional).

---

## 1. Install Ollama

**Windows / macOS:** download the installer from <https://ollama.com/download>
and run it. Ollama installs as a background service.

**Linux:**
```bash
curl -fsSL https://ollama.com/install.sh | sh
```

Verify it is running:
```bash
ollama --version
```

---

## 2. Pull a tool-calling-capable model

The agent uses structured outputs (PydanticAI validation). The model
must support tool calls. Recommended options (smallest first):

| Model | Size | Tool calls |
|---|---|---|
| `qwen2.5:7b` | ~4.7 GB | Yes |
| `llama3.1:8b` | ~4.9 GB | Yes |
| `mistral:7b` | ~4.1 GB | Partial — may need retries |

Pull your chosen model (example with `qwen2.5:7b`):
```bash
ollama pull qwen2.5:7b
```

Verify it loads:
```bash
ollama run qwen2.5:7b "Reply with one word: hello"
```

---

## 3. Configure `.env`

Edit `.env` (copy from `.env.example` if it does not exist):

```env
LLM_PROVIDER=ollama
LLM_MODEL=qwen2.5:7b
UTILITY_MODEL=qwen2.5:7b
OLLAMA_BASE_URL=http://localhost:11434/v1
```

Leave `ANTHROPIC_API_KEY` blank or omit it — it is not used when
`LLM_PROVIDER=ollama`.

---

## 4. Smoke-test the agent on one bug

Before running the full benchmark, verify structured output works with
the chosen model:

```bash
uv run python -m zeroops.runner --error-file eval/fixtures/bug1_error.txt
```

**What to look for:**
- Each node panel renders (Triage, Planner, Tool Executor, Evaluator, …)
- A Postmortem renders at the end
- No `ValidationError` after every tool call

**If validation fails frequently:** smaller models struggle with strict
JSON. Try `llama3.1:8b` instead, or add `--max-retries 2` (the agent
already retries once automatically). Record failure counts in the results.

---

## 5. Run the benchmark (Phase A + Phase B)

```bash
uv run python -m eval.benchmark
```

**Expected run time:** 15–45 minutes depending on GPU and model size.

The benchmark runs two phases automatically:
- **Phase A** — bugs 1, 2, 3, 5 against empty memory; each resolved
  incident is persisted to SQLite
- **Phase B** — bug 4 against the now-populated memory; a correct system
  routes it to L0 (no re-investigation)

Results are written to `eval/results/<UTC-timestamp>/`:
- `results.json` — per-bug metrics + run metadata (provider, model, git hash, timestamp)
- `results.md` — the same table in Markdown

---

## 6. Run the ablation (--no-memory flag, Task T4)

The ablation disables the memory lookup for bug 4, forcing investigation
even though bug 1's pattern is already in memory. Compare the two runs
to quantify the value of episodic memory.

```bash
# Default (with memory)
uv run python -m eval.benchmark

# Ablation (without memory)
uv run python -m eval.benchmark --no-memory
```

Both runs write separate results files. The `condition` field in
`results.json` will be `"with_memory"` or `"no_memory"`.

**Recommended:** run each condition 3 times and report the spread, since
local models are non-deterministic. With n = 5 bugs, report counts like
"4/5 correct" with the sample size stated, never bare percentages.

---

## 7. Comparing Anthropic vs Ollama

If you have Anthropic API access (trial credit or subscription), run the
benchmark again with `LLM_PROVIDER=anthropic` and the model of your
choice. The results file includes the provider and model name, so you
can directly compare rows in the results table.

```env
LLM_PROVIDER=anthropic
LLM_MODEL=claude-sonnet-5-5
UTILITY_MODEL=claude-haiku-5-5
ANTHROPIC_API_KEY=sk-ant-...
```

---

## 8. Commit and use the results

After running, commit the results files:

```bash
git add eval/results/
git commit -m "results: benchmark run with <provider>/<model>"
```

The README's Evaluation section is generated from `eval/results/` files.
Once results are committed, run:

```bash
uv run python -m eval.summarize_results
```

(Implemented as part of T6 — see HANDOFF.md.)

---

## Troubleshooting

| Symptom | Fix |
|---|---|
| `UserError: Set the OLLAMA_BASE_URL env var` | Check `.env` has `OLLAMA_BASE_URL=http://localhost:11434/v1` |
| `ValidationError` on every node | Model does not follow JSON schema; try a larger model |
| Ollama not responding | Run `ollama serve` in a terminal; check port 11434 is free |
| Embedding model download on first run | Expected; `all-MiniLM-L6-v2` caches after first download |
| `incidents.db` already has data | Run `uv run python -c "from zeroops.memory.store import reset_db; reset_db()"` to clear it |
