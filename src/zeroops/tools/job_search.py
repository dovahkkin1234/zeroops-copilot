"""Job-search demo — embedding-based job ranking.

DEMO — self-authored sample postings, not real listings.
No accuracy claims without a committed evaluation.

Reuses the same all-MiniLM-L6-v2 embedding stack as the incident memory
to show the retrieval mechanism generalises to a different domain.

Usage:
    uv run python -m zeroops.tools.job_search "query text"
    uv run python -m zeroops.tools.job_search "LLM engineering Python RAG" --top 5
"""

from __future__ import annotations

import sys
from dataclasses import dataclass

import numpy as np

# Lazy import of embedding utilities — model loads on first search() call.
from ..memory.embeddings import embed, cosine_similarity


# ── Sample job postings (self-authored for demo purposes) ─────────────────────
# Each posting: title, company (fictional), skills list, and a short description.

@dataclass(frozen=True)
class JobPosting:
    id: int
    title: str
    company: str
    skills: list[str]
    description: str

    def as_embedding_text(self) -> str:
        """Concatenate all fields into a single string for embedding."""
        return f"{self.title}. {self.company}. Skills: {', '.join(self.skills)}. {self.description}"


SAMPLE_JOBS: list[JobPosting] = [
    JobPosting(
        id=1,
        title="LLM Engineer — Intern",
        company="Elara AI (fictional)",
        skills=["Python", "LLM agents", "structured outputs", "tool use", "PydanticAI"],
        description=(
            "Build and evaluate LLM agent pipelines for document Q&A and task automation. "
            "Experiment with structured outputs, tool-calling patterns, and prompt engineering. "
            "Work with OpenAI-compatible local models (Ollama) and cloud providers."
        ),
    ),
    JobPosting(
        id=2,
        title="ML Engineer — Retrieval Systems",
        company="Vektra Labs (fictional)",
        skills=["Python", "embeddings", "RAG", "vector search", "FAISS", "sentence-transformers"],
        description=(
            "Design and ship retrieval-augmented generation pipelines for enterprise search. "
            "Own the embedding model selection, indexing, and recall/precision evaluation. "
            "Experience with sentence-transformers, cosine similarity, and chunking strategies."
        ),
    ),
    JobPosting(
        id=3,
        title="AI Research Intern — NLP",
        company="Meridian Research (fictional)",
        skills=["Python", "NLP", "transformers", "PyTorch", "evaluation", "LLM evals"],
        description=(
            "Run experiments on instruction-tuned language models, design LLM eval suites, "
            "and contribute to papers on reasoning and robustness. "
            "Comfortable with Hugging Face transformers and writing reproducible eval code."
        ),
    ),
    JobPosting(
        id=4,
        title="Backend Engineer — Python / FastAPI",
        company="Nuvola Systems (fictional)",
        skills=["Python", "FastAPI", "SQLite", "PostgreSQL", "REST APIs", "async"],
        description=(
            "Build REST APIs for a SaaS incident-management product. "
            "Implement async endpoints with FastAPI, write SQL migrations, and integrate "
            "with third-party webhooks. Light DevOps: Docker, CI/CD."
        ),
    ),
    JobPosting(
        id=5,
        title="Data Engineer — Pipelines",
        company="Prism Analytics (fictional)",
        skills=["Python", "SQL", "dbt", "Airflow", "Spark", "data warehousing"],
        description=(
            "Design and maintain ETL pipelines from production databases to a Snowflake "
            "data warehouse. Write dbt models, schedule with Airflow, and partner with "
            "analytics teams on query optimization."
        ),
    ),
    JobPosting(
        id=6,
        title="Frontend Engineer — React / TypeScript",
        company="Cobalt UI (fictional)",
        skills=["TypeScript", "React", "CSS", "Vite", "Storybook", "accessibility"],
        description=(
            "Own the component library and design-system integration for a B2B SaaS dashboard. "
            "Write accessible, responsive components in TypeScript/React, contribute to "
            "Storybook, and partner with design on new features."
        ),
    ),
    JobPosting(
        id=7,
        title="DevOps / Platform Engineer",
        company="Argent Cloud (fictional)",
        skills=["Docker", "Kubernetes", "Terraform", "CI/CD", "GCP", "observability"],
        description=(
            "Build and operate the deployment platform used by product teams. "
            "Manage Kubernetes clusters on GCP, write Terraform modules, set up "
            "GitHub Actions pipelines, and own SLO monitoring with Grafana."
        ),
    ),
    JobPosting(
        id=8,
        title="AI Platform Engineer",
        company="Korova Tech (fictional)",
        skills=["Python", "LLM tooling", "LangChain", "LangGraph", "Redis", "API design"],
        description=(
            "Build the shared LLM infrastructure layer: prompt management, model routing, "
            "rate-limit handling, and streaming APIs. Partner with product teams to "
            "integrate agent workflows into the main platform."
        ),
    ),
    JobPosting(
        id=9,
        title="iOS Developer — Swift",
        company="Lumino Mobile (fictional)",
        skills=["Swift", "SwiftUI", "UIKit", "Core Data", "Combine", "App Store"],
        description=(
            "Ship features on a consumer iOS app with 500K+ users. "
            "Write SwiftUI views, integrate REST APIs, and optimize for performance "
            "and battery life. Experience with App Store review cycles."
        ),
    ),
    JobPosting(
        id=10,
        title="Database Reliability Engineer",
        company="Stratum DB (fictional)",
        skills=["PostgreSQL", "MySQL", "SQL tuning", "replication", "backup", "monitoring"],
        description=(
            "Own reliability and performance for a fleet of PostgreSQL and MySQL "
            "clusters serving 10M queries/day. Write runbooks, tune slow queries, "
            "set up replication, and manage backup/restore procedures."
        ),
    ),
    JobPosting(
        id=11,
        title="Full-Stack Engineer — Python + React",
        company="Tectonic Apps (fictional)",
        skills=["Python", "Django", "React", "TypeScript", "PostgreSQL", "Docker"],
        description=(
            "Build product features across the stack: Django REST APIs, React frontends, "
            "and PostgreSQL schemas. Work in a small team where every engineer ships "
            "end-to-end. Some DevOps via Docker and GitHub Actions."
        ),
    ),
    JobPosting(
        id=12,
        title="Conversational AI Engineer",
        company="Speakr Labs (fictional)",
        skills=["Python", "dialogue systems", "LLM", "intent classification", "embeddings", "evaluation"],
        description=(
            "Design and ship conversational AI features: intent classification, retrieval "
            "from a knowledge base, and LLM-powered response generation. Write evaluation "
            "harnesses, analyse failure modes, and iterate on prompt design."
        ),
    ),
]


def search(query: str, k: int = 5) -> list[tuple[float, JobPosting]]:
    """Embed query, rank SAMPLE_JOBS by cosine similarity, return top-k.

    Returns list of (score, posting) tuples, highest score first.
    """
    query_vec = embed(query)

    scored: list[tuple[float, JobPosting]] = []
    for posting in SAMPLE_JOBS:
        job_vec = embed(posting.as_embedding_text())
        score = cosine_similarity(query_vec, job_vec)
        scored.append((score, posting))

    scored.sort(key=lambda x: x[0], reverse=True)
    return scored[:k]


def _print_results(results: list[tuple[float, JobPosting]], query: str) -> None:
    try:
        from rich.console import Console
        from rich.table import Table
        from rich import box

        console = Console()
        console.print(f"\n[bold]Job search[/bold] — query: [italic]{query!r}[/italic]")
        console.print("[dim]DEMO — self-authored sample postings, not real listings.[/dim]\n")

        table = Table(box=box.SIMPLE_HEAD, show_lines=False)
        table.add_column("Rank", style="dim", width=4, justify="right")
        table.add_column("Score", width=6, justify="right")
        table.add_column("Title", style="bold", min_width=30)
        table.add_column("Company", style="dim", min_width=20)
        table.add_column("Skills (top 3)")

        for rank, (score, job) in enumerate(results, 1):
            table.add_row(
                str(rank),
                f"{score:.3f}",
                job.title,
                job.company,
                ", ".join(job.skills[:3]),
            )

        console.print(table)
    except ImportError:
        print(f"\nJob search: {query!r}")
        print("DEMO — self-authored sample postings, not real listings.\n")
        for rank, (score, job) in enumerate(results, 1):
            print(f"  {rank}. [{score:.3f}] {job.title} — {job.company}")
            print(f"       Skills: {', '.join(job.skills[:3])}")


def main() -> None:
    import argparse

    parser = argparse.ArgumentParser(
        description=(
            "Embedding-based job ranking demo. "
            "DEMO — self-authored sample postings, not real listings."
        )
    )
    parser.add_argument("query", help="Job-search query (skills, role, interests)")
    parser.add_argument("--top", type=int, default=5, metavar="K",
                        help="Number of results to return (default: 5)")
    args = parser.parse_args()

    results = search(args.query, k=args.top)
    _print_results(results, args.query)


if __name__ == "__main__":
    main()
