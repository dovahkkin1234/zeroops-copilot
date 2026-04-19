# ZeroOps Copilot

> Full README will be written after evaluation metrics are captured (Phase 9).
> See `instructions.md` Section 15 for the template.

## Quickstart

```bash
uv sync
cp .env.example .env  # fill in ANTHROPIC_API_KEY
uv run python -m zeroops.runner --error-file eval/fixtures/bug1_error.txt
```
