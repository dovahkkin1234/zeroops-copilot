# UNTESTED — Docker Desktop was not installed on the build machine.
# Verify with: docker build -t zeroops-copilot . && docker run --rm zeroops-copilot

FROM python:3.11-slim

# ── System deps ───────────────────────────────────────────────────────────────
RUN apt-get update && apt-get install -y --no-install-recommends \
    git \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# ── CPU-only torch first ──────────────────────────────────────────────────────
# Default torch from PyPI includes CUDA (~2 GB). The CPU wheel is ~200 MB.
# Install before sentence-transformers so pip does not pull the CUDA version.
RUN pip install --no-cache-dir \
    torch==2.6.0+cpu \
    --index-url https://download.pytorch.org/whl/cpu

# ── Project runtime deps ──────────────────────────────────────────────────────
RUN pip install --no-cache-dir \
    "openai>=1.0" \
    "langgraph>=0.4.0,<2.0" \
    "pydantic-ai>=1.0.0" \
    "pydantic>=2.0" \
    "pydantic-settings>=2.0" \
    "networkx>=3.0" \
    "sentence-transformers>=2.5" \
    "numpy>=1.24" \
    "gitpython>=3.1" \
    "python-dotenv>=1.0" \
    "rich>=13.0" \
    "typer>=0.12" \
    "fastapi>=0.110" \
    "uvicorn>=0.29" \
    "sse-starlette>=2.0"

# ── Dev/test deps ─────────────────────────────────────────────────────────────
RUN pip install --no-cache-dir \
    "pytest>=8.0" \
    "pytest-asyncio>=0.23" \
    "requests>=2.31"

# ── Project source ────────────────────────────────────────────────────────────
COPY src/ src/
COPY tests/ tests/
COPY eval/ eval/
COPY demo_repo/ demo_repo/
COPY pyproject.toml .

# PYTHONPATH so `import zeroops` resolves without an editable install
ENV PYTHONPATH=/app/src

# ── Pre-download embedding model ──────────────────────────────────────────────
# Stored in /app/.cache at build time so test runs are fully offline.
ENV HF_HOME=/app/.cache/huggingface
ENV TRANSFORMERS_CACHE=/app/.cache/huggingface/hub
RUN python -c "from sentence_transformers import SentenceTransformer; SentenceTransformer('all-MiniLM-L6-v2')"

# ── Non-root user ─────────────────────────────────────────────────────────────
RUN useradd -m -u 1001 appuser && chown -R appuser:appuser /app
USER appuser

# ── Runtime env ───────────────────────────────────────────────────────────────
# OLLAMA_BASE_URL is intentionally NOT set here so the config default
# (localhost:11434/v1) passes the offline test suite.
# Pass it at runtime: docker run -e OLLAMA_BASE_URL=http://host.docker.internal:11434/v1
# or via docker-compose.yml (already configured there).
ENV LLM_PROVIDER=ollama
ENV LLM_MODEL=qwen2.5:7b
ENV UTILITY_MODEL=qwen2.5:7b
ENV EMBED_MODEL=all-MiniLM-L6-v2
ENV DB_PATH=/tmp/incidents.db
ENV REPO_PATH=/app/demo_repo
ENV REPRO_EXECUTION_ENABLED=false

# Default: run offline test suite (no Ollama needed)
CMD ["python", "-m", "pytest", "-q"]
