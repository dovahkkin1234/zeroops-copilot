# ZeroOps Copilot — Claude Code Instruction Manual

> This file is persistent context for Claude Code. Read it fully before any task. When executing phases, re-read the section for that phase. When debugging, re-read the relevant prompt and schema sections.

---

## 0. Who you are and what you're building

You are Claude Code, operating inside the Antigravity IDE. Your user is an intern applicant to **Lumiq.ai** building a 3-day submission for their AI Engineering Internship assignment. The submission is due **9:00 AM IST, April 21, 2026**.

The project is **ZeroOps Copilot** — a multi-agent prototype that demonstrates the industry's shift from reactive incident management to proactive ticket prevention, aligned with the ZeroOps direction that enterprise AMS providers (Cognizant, Infosys, LTIMindtree) are pursuing.

This submission is **Option C** of the Lumiq assignment ("your own idea — any multi-step autonomous workflow solving a real ops problem").

---

## 1. Core principles you must follow at all times

These are non-negotiable. They come from the user's "context engineer, not prompt engineer" philosophy.

1. **Prompts are assets, not strings.** Every node prompt lives in its own `.md` file under `src/zeroops/prompts/`. Python code loads them at startup. Never hardcode a prompt in Python.

2. **Structured outputs everywhere.** Every LLM call produces a PydanticAI-validated object. No free-form text outputs in the agent graph. Free-form rendering happens only in the final Reporter node, which still returns a `Postmortem` object plus a Markdown string.

3. **Tools are plain functions.** Tool implementations in `src/zeroops/tools/*.py` are ordinary Python with type hints and docstrings. They do not know about LangGraph. Nodes call them directly.

4. **The evaluator loop is sacred.** The Investigator's Evaluator node is what makes this an agent rather than a chain. It decides after every tool call whether to continue, hypothesize, or give up. "Give up" is a first-class outcome. Never remove or short-circuit this node.

5. **One LangGraph, three agents, shared tool belt and memory.** Do not build three separate projects. The three agents are sub-graphs/nodes in one LangGraph with one shared `AgentState`, one shared tool catalog, and one shared SQLite memory.

6. **Test end-to-end as early as possible.** Get bug 1 flowing through the full pipeline with stub nodes before polishing any one node. Integration bugs cost more than node-quality bugs.

7. **Fail gracefully in scope.** If you run behind schedule, drop features in this order: (a) Next.js frontend → CLI only, (b) Docker sandbox for repro → show the script without running it, (c) Problem Manager → submit with Triage + Investigator only. Do not drop the Evaluator loop, the Triage, or the memory store under any circumstance.

8. **Use Claude models exclusively.** `claude-opus-4-7` for all agent reasoning nodes. Never fall back to other providers. The Lumiq JD is Claude-heavy and using other models undermines the submission.

---

## 2. The decisions already made (do not re-ask)

| Topic | Decision | Rationale |
|---|---|---|
| LLM provider | Anthropic, `claude-opus-4-7` | Lumiq is Claude-heavy. Opus 4.7 is current flagship. |
| Cheaper utility calls | `claude-haiku-4-5-20251001` if needed | Reserve for non-reasoning formatting tasks only. |
| Package manager | `uv` | Modern, fast, signals current practice. |
| Embeddings | `sentence-transformers` `all-MiniLM-L6-v2`, local | Free, deterministic, no API dependency, demo-reliable. |
| Frontend | FastAPI backend + Next.js App Router — **stretch goal only** | CLI with `rich` is the primary demo path. |
| Demo bugs | Locked list in Section 9 | Two share a pattern to demonstrate Triage L0 and Problem Manager. Do not swap. |
| Python | 3.11+ | PydanticAI requires it. |
| Repo scope | Single-service Python, synchronous stack traces only | Explicitly scoped out: distributed traces, async bugs, infra failures. |

If the user asks about any of these, the decision stands unless they explicitly override it in a follow-up instruction.

---

## 3. The strategic framing (use this voice in README and video)

The user has spoken with a senior engineering manager at Cognizant who framed the problem this way. Use this framing verbatim in the README opening and the video script.

**The industry context.** Application Management Services (AMS) — the business of keeping enterprise software running — is the single largest line item in most IT services contracts. Tickets are stratified across tiers:

- **L0** — self-service (knowledge base, bot). No human touch.
- **L1** — first-line human: basic troubleshooting, scripted fixes.
- **L2** — deeper technical: functional and configuration analysis.
- **L3** — developer-level: code changes, deep debugging.
- **L4** — vendor escalation.

Each tier escalation roughly doubles the cost. The economic game is **shift-left**: push tickets leftward down the tiers until routine failures create no ticket at all.

**ZeroOps** is the target end-state: a mode of operations where intelligent automation has pushed enough tickets leftward that developers spend ~zero time on infrastructure/ops and the human team focuses on novel, high-judgment work. Unlike NoOps (fully human-free, still aspirational), ZeroOps keeps humans in the loop for novel cases and uses automation for everything repeatable.

**Ticket types** (ITIL taxonomy):
- **Incident** — something broke, restore service. (Our Investigator handles this.)
- **Service Request** — user wants access/password/report. (Future scope.)
- **Problem** — the underlying cause of recurring incidents. (Our Problem Manager handles this.)
- **Change Request** — planned modification. (Future scope.)

**The key insight.** Incidents flow from Problems. If you resolve a Problem (the underlying cause), you eliminate a whole class of future Incidents. Most "AI for IT" tools address one layer of this — a chatbot for L0 deflection or an RCA assistant for L3. Real ZeroOps needs a coordinated system. That is what this project prototypes.

---

## 4. System architecture

```
Error text (stack trace, log, or user complaint)
       │
       ▼
  ┌────────────────────────────────────────────────┐
  │  LangGraph StateGraph (src/zeroops/graph.py)   │
  │                                                 │
  │  [Triage Agent]                                 │
  │     │ classify: known_pattern | novel          │
  │     │ If known (similarity ≥ 0.85) → Reporter  │
  │     ▼                                           │
  │  [Investigator Sub-graph]                       │
  │     Planner → Tool Executor → Evaluator         │
  │        ▲_________ loop (max 8) _________│      │
  │     Hypothesizer → Verifier                     │
  │     │                                           │
  │     ▼                                           │
  │  [Problem Manager]                              │
  │     │ scan codebase for same pattern           │
  │     │ produce N prevention tickets              │
  │     ▼                                           │
  │  [Reporter]                                     │
  │     │ Postmortem (PydanticAI) + Markdown       │
  │     ▼                                           │
  │  Memory write (SQLite + embedding)              │
  └────────────────────────────────────────────────┘
```

**Three agents, one graph, shared substrate:**
- Shared `AgentState` TypedDict flows through every node.
- Shared tool catalog in `src/zeroops/tools/`: `read_file`, `grep_code`, `find_tests`, `git_log`, `git_show`, `run_repro`, `search_past_incidents`, `save_incident`.
- Shared SQLite incident memory with sentence-transformer embeddings.
- Every resolved incident is written to memory so the next similar occurrence hits Triage's L0 path.

---

## 5. Repository structure (create exactly this)

```
zeroops-copilot/
├── README.md                         # see section 15
├── pyproject.toml                    # uv-managed
├── .env.example
├── .gitignore
│
├── CLAUDE.md                         # this file
│
├── src/zeroops/
│   ├── __init__.py
│   ├── config.py                     # Settings via pydantic-settings
│   ├── models.py                     # All PydanticAI schemas (section 7)
│   ├── state.py                      # LangGraph AgentState (section 7)
│   │
│   ├── tools/
│   │   ├── __init__.py
│   │   ├── code.py                   # read_file, grep_code, find_tests
│   │   ├── git.py                    # git_log, git_show
│   │   ├── repro.py                  # propose_repro, run_repro
│   │   └── memory.py                 # search_past_incidents, save_incident
│   │
│   ├── memory/
│   │   ├── __init__.py
│   │   ├── store.py                  # SQLite schema + CRUD
│   │   └── embeddings.py             # sentence-transformers wrapper
│   │
│   ├── agents/
│   │   ├── __init__.py
│   │   ├── triage.py                 # Triage node
│   │   ├── investigator.py           # Investigator sub-graph
│   │   ├── problem_manager.py        # Problem Manager node
│   │   └── reporter.py               # Reporter node
│   │
│   ├── prompts/                      # EVERY prompt is a .md file here
│   │   ├── triage.md
│   │   ├── planner.md
│   │   ├── evaluator.md
│   │   ├── hypothesizer.md
│   │   ├── verifier.md
│   │   ├── reporter.md
│   │   └── problem_manager.md
│   │
│   ├── graph.py                      # assembles full LangGraph
│   ├── runner.py                     # CLI entry point (rich-formatted)
│   └── server.py                     # FastAPI (stretch goal)
│
├── demo_repo/                        # seeded toy repo with 5 bugs (section 9)
│   ├── app.py
│   ├── auth.py
│   ├── middleware.py
│   ├── db.py
│   ├── utils.py
│   └── tests/
│       └── test_auth.py
│
├── eval/
│   ├── benchmark.py                  # runs agent on 5 fixtures
│   └── fixtures/
│       ├── bug1_error.txt
│       ├── bug2_error.txt
│       ├── bug3_error.txt
│       ├── bug4_error.txt
│       └── bug5_error.txt
│
├── web/                              # Next.js frontend (STRETCH GOAL)
│   ├── package.json
│   ├── app/
│   │   ├── page.tsx
│   │   └── api/investigate/route.ts
│   └── components/
│       └── ReasoningStream.tsx
│
└── docs/
    ├── architecture.png
    └── ams_glossary.md
```

---

## 6. Dependencies (`pyproject.toml`)

```toml
[project]
name = "zeroops-copilot"
version = "0.1.0"
requires-python = ">=3.11"
dependencies = [
    "anthropic>=0.40.0",
    "langgraph>=0.4.0,<2.0",
    "pydantic-ai>=1.0.0",
    "pydantic>=2.0",
    "pydantic-settings>=2.0",
    "sentence-transformers>=2.5",
    "numpy>=1.24",
    "gitpython>=3.1",
    "python-dotenv>=1.0",
    "rich>=13.0",
    "typer>=0.12",
    "fastapi>=0.110",           # stretch
    "uvicorn>=0.29",            # stretch
    "sse-starlette>=2.0",       # stretch
]

[tool.uv]
dev-dependencies = [
    "pytest>=8.0",
    "pytest-asyncio>=0.23",
]
```

`.env.example`:
```
ANTHROPIC_API_KEY=sk-ant-...
LLM_MODEL=claude-opus-4-7
UTILITY_MODEL=claude-haiku-4-5-20251001
EMBED_MODEL=all-MiniLM-L6-v2
DB_PATH=./incidents.db
REPO_PATH=./demo_repo
MAX_INVESTIGATION_LOOPS=8
REPRO_EXECUTION_ENABLED=false
```

### `src/zeroops/config.py` implementation note

PydanticAI requires model strings with a provider prefix (`anthropic:model-id`). Config must construct these:

```python
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    anthropic_api_key: str
    llm_model: str = "claude-opus-4-7"
    utility_model: str = "claude-haiku-4-5-20251001"
    embed_model: str = "all-MiniLM-L6-v2"
    db_path: str = "./incidents.db"
    repo_path: str = "./demo_repo"
    max_investigation_loops: int = 8
    repro_execution_enabled: bool = False

    @property
    def pydantic_ai_model(self) -> str:
        """PydanticAI needs 'anthropic:model-id' format."""
        return f"anthropic:{self.llm_model}"

    @property
    def pydantic_ai_utility_model(self) -> str:
        return f"anthropic:{self.utility_model}"

    class Config:
        env_file = ".env"


settings = Settings()
```

All agent nodes import `settings.pydantic_ai_model` — never construct model strings inline.

---

## 7. PydanticAI models and LangGraph state

### `src/zeroops/models.py`

```python
from pydantic import BaseModel, Field
from typing import Literal, Optional
from enum import Enum


class TicketTier(str, Enum):
    L0_SELFSERVE = "L0"
    L1_TRIAGE = "L1"
    L2_ANALYSIS = "L2"
    L3_DEEPDIVE = "L3"


class Severity(str, Enum):
    SEV1 = "SEV1"  # outage, data loss, security breach
    SEV2 = "SEV2"  # major feature broken, many users affected
    SEV3 = "SEV3"  # minor feature broken, workaround exists
    SEV4 = "SEV4"  # cosmetic, log noise


class TriageDecision(BaseModel):
    classification: Literal["known_pattern", "novel", "insufficient_info"]
    matched_incident_id: Optional[int] = None
    match_confidence: float = Field(ge=0.0, le=1.0)
    error_type: str
    suggested_tier: TicketTier
    severity: Severity
    routing_reason: str


class EvidenceItem(BaseModel):
    source: Literal["file", "git_commit", "test", "past_incident"]
    reference: str
    observation: str
    relevance: float = Field(ge=0.0, le=1.0)


class PlannerDecision(BaseModel):
    tool: Literal["read_file", "grep_code", "find_tests", "git_log", "git_show"]
    arguments: dict
    reasoning: str


class EvaluatorDecision(BaseModel):
    decision: Literal["continue", "hypothesize", "give_up"]
    confidence: float = Field(ge=0.0, le=1.0)
    reasoning: str


class Hypothesis(BaseModel):
    statement: str
    pattern: Optional[str] = None
    evidence: list[EvidenceItem]
    confidence: float = Field(ge=0.0, le=1.0)


class ReproScript(BaseModel):
    language: Literal["python", "bash"]
    code: str
    expected_error: str
    executed: bool = False
    execution_stdout: Optional[str] = None
    execution_stderr: Optional[str] = None
    reproduced: Optional[bool] = None


class PreventionTicket(BaseModel):
    location: str                        # "file.py:42"
    pattern_match: str                   # why we flagged this
    proposed_fix: str                    # textual description
    proposed_diff: Optional[str] = None
    confidence: float = Field(ge=0.0, le=1.0)


class Postmortem(BaseModel):
    incident_id: int
    resolution_status: Literal["resolved", "known_pattern", "uncertain"]
    triage: TriageDecision
    timeline: list[str]
    hypothesis: Optional[Hypothesis] = None   # None for L0 fast-path
    repro: Optional[ReproScript] = None
    root_cause: str
    proposed_fix: str
    proposed_diff: Optional[str] = None       # None for L0 and uncertain paths
    prevention_tickets: list[PreventionTicket] = Field(default_factory=list)
    confidence: float = Field(ge=0.0, le=1.0)
    failure_reason: Optional[str] = None      # populated when resolution_status == "uncertain"
    tools_called: int                         # derived from len(tool_history) in state
    duration_seconds: float
    markdown: str                             # human-readable render
```

### `src/zeroops/state.py`

```python
from typing import TypedDict, Annotated, Optional
from operator import add


class AgentState(TypedDict):
    # Input
    error_text: str

    # Triage outputs
    triage: Optional[dict]               # TriageDecision as dict

    # Investigation state
    current_plan: Optional[dict]
    evidence: Annotated[list, add]
    tool_history: Annotated[list[dict], add]  # each entry: {tool, args, result_summary}

    # Loop control
    iteration: int
    max_iterations: int
    evaluator_decision: Optional[str]    # continue | hypothesize | give_up

    # Hypothesis + verification
    hypothesis: Optional[dict]
    repro: Optional[dict]

    # Problem manager output
    prevention_tickets: Annotated[list, add]

    # Final output
    postmortem: Optional[dict]
    duration_seconds: Optional[float]
```

---

## 8. The node prompts (context engineering artifacts — MOST IMPORTANT SECTION)

Each of these goes into its own file under `src/zeroops/prompts/`. Every agent node loads its prompt at import time. Never inline these prompts into Python.

### `prompts/triage.md`

```
# ROLE
You are the Triage Agent in a ZeroOps incident response system.
Your job is to classify incoming errors and route them to the cheapest
resolution path that still solves the problem correctly.

# TASK
Given a raw error (stack trace, log, or user complaint), decide:
1. What kind of error is this? (error_type, severity)
2. Have we seen this pattern before? (semantic similarity search results
   are provided to you.)
3. If yes and confidence is high, route to L0 auto-resolve.
4. If no, or confidence is insufficient, route to the Investigator (L2/L3).

# INPUT
<error>
{error_text}
</error>

<past_incident_matches>
{top_3_matches_with_similarity_scores}
</past_incident_matches>

# DECISION RULES
- If top match similarity >= 0.85 AND same error_type: classify as
  "known_pattern". Set suggested_tier = L0. Cite matched_incident_id.
- If top match similarity in [0.70, 0.85]: classify as "novel" but note the
  suggestive match in routing_reason — the Investigator will use this as a
  starting hypothesis.
- If no meaningful match: classify as "novel", suggested_tier = L2.
- If the error text is too vague to parse: classify as "insufficient_info".

# SEVERITY GUIDE
- SEV1: service unavailable, data loss, security breach
- SEV2: major feature broken, many users affected
- SEV3: minor feature broken, workaround exists
- SEV4: cosmetic, log noise

# OUTPUT FORMAT
Return a valid TriageDecision JSON object. Do not include prose outside
the JSON. Be decisive. "insufficient_info" is only for genuinely
unparseable input, not for cases where you're merely uncertain about
severity.
```

### `prompts/planner.md`

```
# ROLE
You are the Planner node of an autonomous investigation agent. You
decide the next single action to take based on current evidence.

# TASK
Look at the current state. Choose ONE tool call that will most advance
the investigation. You are not allowed to make multiple tool calls —
only one. The Evaluator will decide whether to loop back to you for
another tool call.

# CURRENT STATE
<error>{error_text}</error>
<triage_hint>{triage_routing_reason}</triage_hint>
<evidence_so_far>{evidence}</evidence_so_far>
<tools_already_called>{tool_history}</tools_already_called>
<iteration>{iteration} of max {max_iterations}</iteration>

# TOOLS AVAILABLE
- read_file(path, start_line?, end_line?) — read source
- grep_code(pattern, path_glob?) — find symbol usages across the repo
- git_log(path, n=10) — recent commits touching a file
- git_show(commit_hash) — see exactly what a commit changed
- find_tests(function_name) — locate tests for a function

# STRATEGY GUIDELINES
Early iterations (1–3): characterize the error. Read the failing file,
find where the problematic symbol is defined vs. used.
Middle iterations (3–6): check git history for recent changes. Symbol
mismatches are very often from incomplete refactors.
Late iterations (6+): check tests, check callers of related functions.
Never call the same tool with the same arguments twice — the Evaluator
will penalize redundancy.

# OUTPUT FORMAT
Return a valid PlannerDecision JSON with tool, arguments, reasoning.
The reasoning must be one sentence explaining what hypothesis you're
testing with this call.
```

### `prompts/evaluator.md`

```
# ROLE
You are the Evaluator node. You are the agentic heart of this system.
After each tool call, you decide whether we have enough evidence to form
a confident hypothesis, or whether further investigation is needed.

# YOU ARE NOT THE PLANNER.
Do not propose new tool calls. Do not investigate. Your only job is to
decide the routing.

# INPUT
<error>{error_text}</error>
<evidence>{evidence}</evidence>
<iteration>{iteration} of max {max_iterations}</iteration>

# DECISION CRITERIA

Return "hypothesize" when ALL of the following hold:
- At least one piece of evidence directly identifies a code defect
  (wrong symbol, missing check, stale reference, etc.)
- The defect explains the observed error mechanistically
- You can write a one-sentence hypothesis without hedging

Return "continue" when:
- Evidence points to a region but the specific defect isn't pinpointed
- A key tool (git_log, grep_code) hasn't been tried yet
- We're below iteration 6

Return "give_up" when:
- iteration >= max_iterations
- Evidence is contradictory
- OR you cannot form a hypothesis with confidence >= 0.5

"give_up" is a FIRST-CLASS outcome. Honest uncertainty is a feature,
not a bug. A correct "I don't know, here's why" is better than a
confident wrong answer.

# OUTPUT FORMAT
Return a valid EvaluatorDecision JSON with decision, confidence,
reasoning. Keep reasoning to two sentences max.
```

### `prompts/hypothesizer.md`

```
# ROLE
You synthesize the investigation into a single, falsifiable hypothesis.

# INPUT
<error>{error_text}</error>
<evidence>{all_evidence}</evidence>

# TASK
Produce a Hypothesis object. Your hypothesis MUST be falsifiable —
i.e., a repro script could confirm or deny it. Vague hypotheses like
"probably a race condition" are rejected.

# PATTERN TAGGING
Tag your hypothesis with a pattern name from this canonical set (or
propose a new one in the same snake_case style):
- incomplete_symbol_rename
- unchecked_none_return
- type_mismatch_at_boundary
- missing_null_check
- stale_import
- off_by_one
- race_condition
- resource_leak
- unhandled_exception
- config_mismatch

The pattern tag is critical — Problem Manager uses it to find similar
vulnerable code elsewhere in the repo. Pick the most specific tag
that fits.

# OUTPUT FORMAT
Return a Hypothesis JSON object with statement, pattern, evidence
(filter to only items that support the hypothesis), and confidence.
```

### `prompts/verifier.md`

```
# ROLE
You generate a minimal reproduction script that would confirm or deny
the hypothesis. You are doing science: hypothesis -> experiment -> result.

# INPUT
<hypothesis>{hypothesis}</hypothesis>
<relevant_code>{code_snippets_from_evidence}</relevant_code>

# TASK
Write a Python or bash script that:
1. Sets up the minimal environment to trigger the bug
2. Calls the offending code path
3. Will produce the observed error if the hypothesis is correct
4. Is self-contained (no external services, no network)
5. Runs in under 5 seconds

# CONSTRAINTS
- Do NOT attempt to fix the bug in the repro. Only reproduce it.
- Prefer Python unless a shell command is clearly simpler.
- If the repro requires side effects (file writes, env vars), use /tmp
  and clean up afterward.

# OUTPUT FORMAT
Return a valid ReproScript JSON. Set executed=false and reproduced=null;
the execution harness will fill these in if REPRO_EXECUTION_ENABLED is
true.
```

### `prompts/problem_manager.md`

```
# ROLE
You are the Problem Manager Agent. Your role is the proactive layer of
the system. While the Investigator resolves THIS incident, you look for
the same CLASS of bug elsewhere in the codebase so it can be prevented.

This is the ZeroOps bridge: reactive resolution -> proactive prevention.
It is what makes the Cognizant manager's prompt actionable — each
incident resolved becomes N incidents prevented.

# INPUT
<resolved_hypothesis>{hypothesis}</resolved_hypothesis>
<pattern>{pattern_tag}</pattern>
<root_cause>{root_cause}</root_cause>
<repo_root>{repo_path}</repo_root>

# TASK
Based on the pattern tag, scan the codebase for similar vulnerable
code. Your goal is to generate 0 to N Prevention Tickets — each a
specific location where the same bug pattern likely exists.

# PATTERN-SPECIFIC STRATEGIES
- incomplete_symbol_rename: grep for imports of the old symbol name.
  For each hit, check whether the import target still exists. Flag
  mismatches.
- stale_import: grep for the old import name across the repo.
- unchecked_none_return: find all callers of the function; check whether
  each one guards against None.
- missing_null_check: check all call sites of functions that can return
  None or empty.
- type_mismatch_at_boundary: find other callers that pass similar types.

For each candidate location, use grep_code and read_file to verify the
pattern actually applies there before flagging. False positives hurt
trust — be precise.

# OUTPUT FORMAT
Return a JSON array of PreventionTicket objects. Empty array is valid
if no other instances exist. Each ticket needs: location (file:line),
pattern_match (why flagged), proposed_fix (textual), proposed_diff
(optional), confidence.

# CRITICAL
Only flag locations where you have READ the code and VERIFIED the
pattern applies. Speculation is not acceptable. Confidence >= 0.6
minimum.
```

### `prompts/reporter.md`

```
# ROLE
You write the final postmortem in the voice of a thoughtful senior
engineer.

# INPUT
All accumulated state: triage, hypothesis, repro, evidence, prevention
tickets, tools_called, iteration count.

# TASK
Produce a Postmortem JSON object AND a rendered Markdown report.

# MARKDOWN STRUCTURE
1. **Incident Summary** (2 sentences)
2. **Severity and Tier** (one line, cite the SLA implication)
3. **Timeline** (bulleted, chronological investigation trace)
4. **Root Cause** (one paragraph)
5. **Evidence** (table: source | observation | relevance)
6. **Proposed Fix** (code diff in a fenced block)
7. **Reproduction** (the repro script, and whether it was verified)
8. **Prevention Tickets** (one per similar pattern found, with file:line
   and proposed fix)
9. **What This Tells Us** (one paragraph — the systemic takeaway,
   connecting this incident to the broader ZeroOps picture)

# VOICE GUIDELINES
- Write like you're explaining to a colleague, not a customer.
- Be honest about confidence. If verified=False, say so.
- Never overstate. "Likely" and "probably" are okay when warranted.
- End with the prevention perspective: this incident made the system
  safer by N tickets.

# OUTPUT FORMAT
Return a Postmortem JSON object. The markdown field contains the full
rendered report as described above.
```

---

## 9. The demo repo (seeded bugs — DO NOT MODIFY THE PATTERN DESIGN)

The demo repo in `demo_repo/` has 5 bugs. **Bugs 1 and 2 share the `incomplete_symbol_rename` pattern.** This is deliberate and critical for the demo — it is what lets Problem Manager visibly find a second instance after resolving the first, and what lets Triage later L0-resolve a variant.

### `demo_repo/auth.py`

```python
"""Handles token validation."""

def verify_token(token: str) -> bool:
    if not token:
        return False
    return token.startswith("valid_")


def hash_password(password: str) -> str:
    return f"hashed_{password}"
```

### `demo_repo/middleware.py` — BUG 1 (incomplete symbol rename)

```python
"""Request middleware. Calls into auth."""
from auth import validate_token  # BUG: was renamed to verify_token


def require_auth(request):
    token = request.get("token")
    if not validate_token(token):
        raise PermissionError("Auth failed")
    return True
```

### `demo_repo/utils.py`

```python
"""Utility helpers."""

def normalize_text(s: str) -> str:
    return s.strip().lower()


def parse_date(s: str):
    """Returns None for invalid input. Callers must check."""
    try:
        return [int(x) for x in s.split("-")]
    except Exception:
        return None
```

### `demo_repo/db.py` — BUG 2 (same pattern as BUG 1)

```python
"""Database layer. Calls into utils."""
from utils import normalize_string  # BUG: was renamed to normalize_text


def insert_record(table, data):
    clean_data = {k: normalize_string(v) for k, v in data.items()}
    return {"status": "ok", "table": table}
```

### `demo_repo/app.py` — BUG 3 (unchecked_none_return)

```python
"""Main app. Has an unchecked None from parse_date."""
from utils import parse_date


def get_events_on(date_str):
    parts = parse_date(date_str)
    year, month, day = parts  # BUG: parts can be None; TypeError
    return {"year": year}
```

### `demo_repo/tests/test_auth.py` — BUG 5 (stale test, another stale_import instance)

```python
from auth import validate_token  # BUG: stale import, test crashes on collection


def test_valid():
    assert validate_token("valid_abc")
```

### Git seeding (run once during `demo_repo/` setup)

```bash
cd demo_repo
git init
git add auth.py utils.py app.py db.py middleware.py tests/
git commit -m "initial scaffolding with validate_token and normalize_string"
# Commit 2: the refactor that caused bugs 1, 2, and 5
python -c "from pathlib import Path; f=Path('auth.py'); f.write_text(f.read_text().replace('validate_token','verify_token'))"
python -c "from pathlib import Path; f=Path('utils.py'); f.write_text(f.read_text().replace('normalize_string','normalize_text'))"
git add auth.py utils.py
git commit -m "refactor: rename token and string utils for clarity"
# middleware.py, db.py, and tests/test_auth.py were NOT updated — that is the bug
```

### Error fixtures (`eval/fixtures/`)

Each fixture file contains a realistic Python stack trace. File names and expected root causes:

**`bug1_error.txt`** — target pattern: `incomplete_symbol_rename`
```
Traceback (most recent call last):
  File "middleware.py", line 6, in require_auth
    if not validate_token(token):
AttributeError: module 'auth' has no attribute 'validate_token'
```

**`bug2_error.txt`** — target pattern: `incomplete_symbol_rename` (SAME pattern as bug1)
```
Traceback (most recent call last):
  File "db.py", line 2, in <module>
    from utils import normalize_string
ImportError: cannot import name 'normalize_string' from 'utils'
```

**`bug3_error.txt`** — target pattern: `unchecked_none_return`
```
Traceback (most recent call last):
  File "app.py", line 6, in get_events_on
    year, month, day = parts
TypeError: cannot unpack non-iterable NoneType object
```

**`bug4_error.txt`** — variant of bug1 (for Triage L0 demo — run this AFTER bug1 is resolved)
```
Traceback (most recent call last):
  File "handlers.py", line 12, in check_session
    if not validate_token(session_token):
AttributeError: module 'auth' has no attribute 'validate_token'
```

**`bug5_error.txt`** — target pattern: `stale_import`
```
ERROR: collecting tests/test_auth.py
ImportError while importing test module 'tests/test_auth.py'.
    from auth import validate_token
ImportError: cannot import name 'validate_token' from 'auth'
```

Each fixture is paired with an `expected_pattern` and `expected_root_cause_keyword` for benchmark scoring.

---

## 10. Memory store

### `src/zeroops/memory/store.py`

SQLite schema:

```sql
CREATE TABLE IF NOT EXISTS incidents (
    id                  INTEGER PRIMARY KEY AUTOINCREMENT,
    created_at          TEXT NOT NULL,
    error_text          TEXT NOT NULL,
    error_type          TEXT,
    error_signature     TEXT NOT NULL,
    root_cause          TEXT NOT NULL,
    root_cause_pattern  TEXT,
    affected_files      TEXT,                  -- JSON
    fix_summary         TEXT,
    fix_diff            TEXT,
    embedding           BLOB,
    confidence          REAL,
    verified            INTEGER DEFAULT 0
);

CREATE INDEX IF NOT EXISTS idx_pattern ON incidents(root_cause_pattern);
CREATE INDEX IF NOT EXISTS idx_type ON incidents(error_type);
```

Functions to implement:
- `init_db(path: str) -> None`
- `save_incident(incident: dict) -> int` returns id
- `search_similar(query_embedding: np.ndarray, k: int = 3) -> list[tuple[int, float, dict]]`
- `get_by_id(id: int) -> dict | None`

### `src/zeroops/memory/embeddings.py`

- Lazy singleton loader for `sentence-transformers` `all-MiniLM-L6-v2`
- `embed(text: str) -> np.ndarray`
- `cosine_similarity(a: np.ndarray, b: np.ndarray) -> float`
- `serialize(arr: np.ndarray) -> bytes` and `deserialize(blob: bytes) -> np.ndarray` for SQLite storage

**Error signature normalization** — before embedding, strip volatile info (line numbers, file paths become basenames, memory addresses) so semantically identical errors produce identical signatures.

**Memory save contract:**
- Only save incidents where `confidence >= 0.5`.
- Unresolved incidents (`resolution_status == "uncertain"`) are **not** saved to memory — they would poison future L0 matches.
- Embeddings are generated from the **normalized error signature**, not raw `error_text`.
- `affected_files` is stored as a JSON array of file basenames extracted from evidence.
- Duplicate error signatures should **upsert** (update existing row) rather than create new rows.

---

## 11. Tool implementations

All tools are plain functions. They operate on the repo path given by env var `REPO_PATH` (default `./demo_repo`).

### `src/zeroops/tools/code.py`

```python
def read_file(path: str, start_line: int | None = None,
              end_line: int | None = None) -> str:
    """Read a file slice. Returns content with line numbers prefixed.
    Paths are resolved relative to REPO_PATH."""

def grep_code(pattern: str, path_glob: str = "**/*.py") -> list[dict]:
    """Search for regex pattern across files matching glob.
    Returns list of {file, line, text} matches with 2 lines of context."""

def find_tests(function_name: str) -> list[str]:
    """Find test files containing references to a function name.
    Returns list of file paths."""
```

### `src/zeroops/tools/git.py` (use `gitpython`)

```python
def git_log(path: str, n: int = 10) -> list[dict]:
    """Return last N commits touching path.
    Each commit: {hash, author, date, subject}."""

def git_show(commit_hash: str) -> dict:
    """Return {hash, subject, message, diff, files_changed}."""
```

### `src/zeroops/tools/repro.py`

```python
def run_repro(script: str, language: str = "python",
              timeout: int = 5) -> dict:
    """Execute repro in subprocess. Returns {success, stdout, stderr,
    exit_code}. Only runs if REPRO_EXECUTION_ENABLED=true.
    If false, returns {executed: false, reason: 'disabled'}."""
```

The Verifier node generates the script via LLM; this function only runs it.

### `src/zeroops/tools/memory.py`

```python
def search_past_incidents(query_text: str, k: int = 3) -> list[dict]:
    """Embed the query, search SQLite, return top-k with similarity scores."""

def save_incident(postmortem: dict) -> int:
    """Persist a resolved incident to memory. Returns the new id."""
```

---

## 12. Graph assembly (`src/zeroops/graph.py`)

```python
from langgraph.graph import StateGraph, START, END
from .state import AgentState
from .agents.triage import triage_node
from .agents.investigator import (
    planner_node, tool_executor_node, evaluator_node,
    hypothesizer_node, verifier_node
)
from .agents.problem_manager import problem_manager_node
from .agents.reporter import reporter_node


def route_from_triage(state: AgentState) -> str:
    if state["triage"]["classification"] == "known_pattern":
        return "reporter"        # L0 fast path
    return "planner"


def route_from_evaluator(state: AgentState) -> str:
    decision = state["evaluator_decision"]
    if decision == "continue":
        return "planner"
    if decision == "hypothesize":
        return "hypothesizer"
    return "reporter"            # give_up routes to reporter with uncertainty


def build_graph():
    g = StateGraph(AgentState)

    g.add_node("triage", triage_node)
    g.add_node("planner", planner_node)
    g.add_node("tool_executor", tool_executor_node)
    g.add_node("evaluator", evaluator_node)
    g.add_node("hypothesizer", hypothesizer_node)
    g.add_node("verifier", verifier_node)
    g.add_node("problem_manager", problem_manager_node)
    g.add_node("reporter", reporter_node)

    g.add_edge(START, "triage")

    g.add_conditional_edges("triage", route_from_triage,
                            {"reporter": "reporter", "planner": "planner"})

    g.add_edge("planner", "tool_executor")
    g.add_edge("tool_executor", "evaluator")

    g.add_conditional_edges("evaluator", route_from_evaluator, {
        "planner": "planner",
        "hypothesizer": "hypothesizer",
        "reporter": "reporter",
    })

    g.add_edge("hypothesizer", "verifier")
    g.add_edge("verifier", "problem_manager")
    g.add_edge("problem_manager", "reporter")
    g.add_edge("reporter", END)

    return g.compile()
```

**Reporter fast-path rule (L0 path):** When `classification == "known_pattern"`, the Reporter receives state where `hypothesis`, `repro`, `evidence`, and `prevention_tickets` may all be empty/None. In this case, Reporter must generate an L0-style postmortem using **only** the triage result and the matched past incident from memory. Set `resolution_status = "known_pattern"` and populate `root_cause`/`proposed_fix` from the matched incident's stored data. Do not attempt to fill `proposed_diff` or `prevention_tickets`.

**Node integration pattern (reference implementation):**

Every agent node follows this pattern internally:

```python
from pathlib import Path
from pydantic_ai import Agent
from ..config import settings
from ..models import TriageDecision

_prompt = (Path(__file__).parent.parent / "prompts" / "triage.md").read_text()


async def triage_node(state: AgentState) -> dict:
    agent = Agent(
        settings.pydantic_ai_model,     # "anthropic:claude-opus-4-7"
        output_type=TriageDecision,
        system_prompt=_prompt.format(**state),
    )
    result = await agent.run(state["error_text"])
    return {"triage": result.output.model_dump()}
```

**Retry on validation failure:** If PydanticAI validation fails, retry once with a repair prefix: `"Return ONLY valid JSON for schema {schema}. Previous error: {error}"`. If the retry also fails, raise — never silently fall back to unstructured text.

---

## 13. CLI runner (`src/zeroops/runner.py`)

Uses `rich` for live streaming output. This is the primary demo surface.

Required behavior:
- `python -m zeroops.runner --error-file path.txt` or `--error "text"`
- Streams each node's output as a `rich.panel.Panel` as it executes
- Each panel shows: node name, decision/output summary, elapsed time
- Final panel: rendered Markdown postmortem
- Final line: `Tickets prevented: N | Total duration: Xs | Confidence: Y%`

This is what you will demo on video. Make it look good.

**Implementation rule:** Use LangGraph node-level step rendering — print a `rich.panel.Panel` after each node returns. Do **not** attempt token-level streaming in v1. The flow is: invoke graph with per-node callbacks → render each completed node's output as a panel → final panel is the full Markdown postmortem.

---

## 14. Evaluation benchmark (`eval/benchmark.py`)

Runs the agent on all 5 fixtures. Reports:

| Metric | Definition |
|---|---|
| Triage accuracy | % where classification matches expected (known_pattern for bug4 after bug1 is resolved; novel for bugs 1, 2, 3, 5) |
| Investigator pattern accuracy | % where hypothesis.pattern matches expected_pattern |
| Investigator root-cause accuracy | % where root_cause contains expected_root_cause_keyword (substring match) |
| Problem Manager coverage | For bug1, does Problem Manager find bug2's location as a prevention ticket? |
| Tickets prevented / ticket resolved | Sum(prevention_tickets) / 5 |
| Avg tools called | Mean of len(tool_history) per investigation |
| Avg duration | Mean duration_seconds |

Must run with: `uv run python -m eval.benchmark`

**Benchmark execution order (stateful — critical):**

The benchmark MUST run in two phases because bug4 depends on bug1 being resolved and saved to memory first:

1. **Phase A (cold start):** Run bugs 1, 2, 3, 5 against empty memory. Persist all resolved incidents to SQLite after each run.
2. **Phase B (warm memory):** Run bug4 against the now-populated memory. Bug4 should hit the L0 path if bug1 was resolved successfully.

Without this phasing, bug4 cannot demonstrate the Triage L0 fast path and triage accuracy metrics will be inaccurate. Reviewers running `eval.benchmark` must get consistent results.

Output as a `rich.table.Table`.

---

## 15. README template

Use exactly this structure. Fill brackets with actual data after running benchmark.

```markdown
# ZeroOps Copilot

A multi-agent prototype that shifts incident tickets leftward — from L3
investigation to L0 auto-resolution to prevented — aligned with the
industry's ZeroOps direction.

**Submission:** Lumiq AI Engineering Intern Assignment, Option C
**Built by:** [Your Name] · [GitHub] · IIITDM · April 2026

## 30-second pitch

IT tickets are the single largest operational cost center in enterprise
engineering. The industry is shifting to **ZeroOps** — a target state of
zero operational tickets — by pushing tickets leftward down the support
tiers (L3 → L2 → L1 → L0 → prevented). This project is a working
prototype of that architecture: three coordinated agents that triage,
investigate, and prevent recurrence of production incidents.

## Why this framing

I spoke with a senior engineering manager at Cognizant who framed the
ticket-reduction problem as reactive vs. proactive. Most "AI for IT"
tools address one layer — a chatbot for L0 deflection, or an RCA
assistant for L3. Real ZeroOps needs a coordinated system that learns
from every resolution. This project is a working prototype of that
idea, scoped to Python codebases.

## Architecture

![architecture](docs/architecture.png)

Three agents on one LangGraph, sharing state, tools, and memory:

- **Triage Agent** — semantic similarity search against learned incident
  memory. If the pattern matches a resolved incident with ≥ 0.85
  confidence, the ticket is auto-resolved (L0 path). Otherwise it is
  routed to the Investigator with any suggestive hint attached.
- **Investigator Agent** — autonomous multi-tool reasoning loop.
  Planner → Tool Executor → Evaluator, looping until evidence is
  sufficient. Hypothesizer forms a falsifiable theory. Verifier
  generates a minimal repro script. Optional Docker sandbox runs it.
- **Problem Manager Agent** — proactive layer. Takes the resolved
  hypothesis's pattern tag and scans the codebase for other places
  where the same vulnerable pattern exists. Produces Prevention
  Tickets for each verified match.

## The agentic heart: the evaluator loop

After every tool call, a dedicated Evaluator node decides one of three
things: `continue` (we need more evidence), `hypothesize` (we have
enough), or `give_up` (evidence is contradictory or we're out of
budget). `give_up` is a first-class outcome. A correct "I don't know,
here's what I tried" beats a confident wrong answer.

## Hypothesis verification

Before reporting, the Investigator generates a minimal reproduction
script. Optionally (when `REPRO_EXECUTION_ENABLED=true`), it runs the
script in a sandbox and verifies the error actually reproduces.
Hypothesis → experiment → result. Closing this loop is what
distinguishes this from an RCA assistant that stops at plausible
theories.

## Built with

- **Claude Opus 4.7** as the reasoning model for all agent nodes
- **Claude Code** as the primary development agent, inside the
  **Antigravity** IDE — hitting both of Lumiq's named agentic tools
- **LangGraph** for the state-machine orchestration
- **PydanticAI** for strict structured outputs on every node
- **sentence-transformers** (`all-MiniLM-L6-v2`) for local incident
  similarity
- **SQLite** for incident memory
- **`rich`** for the CLI demo; **FastAPI + Next.js** for the streaming
  web UI (optional)

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
Two bugs share the same underlying pattern (`incomplete_symbol_rename`)
— perfect for demonstrating the L0 path after the first resolution, and
for showing Problem Manager finding the second instance proactively.

## Evaluation results

[Filled in after running benchmark.]

| Metric | Value |
|---|---|
| Triage accuracy | [%] |
| Investigator pattern accuracy | [%] |
| Investigator root-cause accuracy | [%] |
| Problem Manager coverage | [fraction] |
| Tickets prevented per ticket resolved | [ratio] |
| Avg tools called per investigation | [count] |
| Avg investigation duration | [seconds] |

## Ticket taxonomy reference

For reviewers unfamiliar with AMS vocabulary:

- **L0**: self-service, no human touch
- **L1**: first-line, scripted troubleshooting
- **L2**: functional and technical analysis
- **L3**: developer-level deep-dive
- Each tier escalation roughly doubles cost. The economic game is
  shift-left.

## Built with Claude Code

This project was scaffolded and iterated on with Claude Code as the
primary development agent, running inside the Antigravity IDE.
Approximately 70% of the code was generated from scoped prompts and
then reviewed/corrected; the architecture, prompt designs, and
integration logic were human-driven. Notable Claude Code usage:

- Phase 1 scaffolding of the full repo structure
- Phase 4 tool implementations (with tests)
- The toy demo repo with git history
- Next.js scaffolding (stretch)

## Limitations (scope boundaries)

- Python only, single-service, synchronous stack traces
- Out of scope: distributed traces, async/timing bugs, data-layer
  issues, infrastructure failures
- Repro execution is sandboxed via subprocess only; a proper Docker
  sandbox is a next step
- Incident memory is local SQLite; a real deployment would need a
  shared vector DB (Pinecone/Qdrant are in Lumiq's named stack)

## What this unlocks next

The three-agent pattern generalizes directly to the full AMS taxonomy:
Service Requests (access/provisioning), Change Management
(deploy-risk scoring), Event Management (alert correlation). The
architecture demonstrated here is a microcosm of what enterprise AMS
providers are building for production in 2026.
```

---

## 16. Video script (target 3:00–3:30)

The user will record this after the build. Keep this script intact — it is optimized for Lumiq's panel.

**[0:00–0:20] Hook**
> "A senior engineering manager at Cognizant told me tickets are the biggest operational cost in enterprise IT, and the industry is shifting to ZeroOps — the target state of zero operational tickets. I built a working prototype of that architecture."
> [Show architecture diagram full-screen]

**[0:20–0:50] Problem framing**
> "AMS — application management services — is how Cognizant, Infosys, and LTIMindtree keep enterprise apps running. The economics are brutal: L1, L2, L3 tickets roughly double in cost at each tier. The industry strategy is to shift tickets leftward — auto-resolve at L0, investigate only what's novel, and most importantly, prevent the next occurrence entirely. Most AI tools attack one layer. I built a system that does all three."

**[0:50–1:30] Architecture walkthrough**
> "Three agents on one LangGraph. Triage does semantic similarity against a learned incident memory — if we've resolved this pattern, we skip straight to the answer. Otherwise, the Investigator runs an autonomous loop: Planner decides the next tool call, Tool Executor runs it, and crucially an Evaluator node decides after each step whether we have enough evidence. This evaluator is the agentic heart — it keeps investigating until confidence crosses a threshold, or honestly gives up. Before reporting, a Verifier generates a minimal repro script to test the hypothesis. Then the Problem Manager scans the codebase for the same pattern elsewhere — that's how one ticket resolved becomes N tickets prevented."

**[1:30–2:45] Live demo**
> [Open the CLI demo. Paste bug1 stack trace.]
> "Production error. AttributeError, auth module, validate_token..."
> [Watch the stream.]
> "Triage says novel, never seen this — passes to Investigator. Planner decides to read auth.py. Evaluator: symbol doesn't exist there, need more. Planner: check git log. Evaluator: found a rename commit two commits ago — enough evidence. Hypothesizer: incomplete_symbol_rename pattern. Verifier writes a 4-line repro. Problem Manager scans for the same pattern — finds another incomplete rename in db.py with normalize_string. Final report: one incident resolved, one future incident prevented."
> [Show the rendered postmortem.]

**[2:45–3:10] Second run — Triage L0 path**
> "Now a second error — same pattern, different file."
> [Paste bug4 — a variant of bug1.]
> "Triage recognized the pattern from memory. Resolved in under 3 seconds, no investigation needed. That's shift-left in action."

**[3:10–3:30] Limitation + next**
> "One limitation: repro verification is toggle-able because sandboxed execution is a project of its own. Next step: full Docker-based verification and generalizing the three-agent pattern to service requests and change management — the full AMS taxonomy."

---

## 17. Hour-by-hour execution timeline

Assume "start now" is Saturday evening April 19. Submission deadline 9 AM April 21.

**Saturday evening (4 hours):**
- Hr 1: Phase 1 — bootstrap `pyproject.toml`, `.env`, structure, empty stubs
- Hr 1–2: Phase 2 — seed `demo_repo/` with git history
- Hr 2–3: Phase 3 — `models.py` and `state.py`
- Hr 3–4: Phase 4 — tool implementations + manual test each on demo_repo

**Sunday (10 hours):**
- Hr 5: Phase 5 — memory store + embeddings
- Hr 6–9: Phase 6 — Investigator sub-graph. HARD PART. Test on bug1 end-to-end before proceeding.
- Hr 10–11: Phase 7 — Triage + Problem Manager + Reporter + full graph assembly
- Hr 12: Run pipeline on all 5 bugs, fix issues
- Hr 13: Phase 8 — CLI runner with `rich` streaming
- Hr 14: Phase 9 — benchmark harness

**Monday morning (5 hours, submit by 9 AM):**
- Hr 15: Buffer / bug fixes from Sunday
- Hr 16: Optional Phase 10 — Next.js frontend IF Hr 14 finished clean
- Hr 17: Record video (script in Section 16)
- Hr 18: Polish README with filled-in metrics, push to GitHub public repo
- Hr 19: Upload video (Loom or YouTube unlisted), submit form

**Stretch-goal degradation order** (drop in this order if behind schedule):
1. Next.js frontend → ship CLI only
2. Docker sandbox for repro → show generated script without running
3. Problem Manager → submit with Triage + Investigator only, note in README

Never drop: Evaluator loop, Triage with memory search, at least one end-to-end working demo bug.

---

## 18. How to work with Claude Code

When the user asks you to do a phase:
1. Read this CLAUDE.md file in full
2. Read only the relevant sections for the phase
3. Before generating any code, write a 3-bullet summary of what you'll do
4. Generate the code for that phase only — do not skip ahead
5. Run whatever tests/smoke checks apply
6. Commit with a descriptive message
7. Report back what you did, what you skipped, and what to test next

**Phase-by-phase prompt starters the user will give you:**

**Phase 1 — Bootstrap:**
> "Phase 1. Scaffold the project per CLAUDE.md section 5 and section 6. Empty stubs only. Commit when done."

**Phase 2 — Demo repo:**
> "Phase 2. Create demo_repo/ per CLAUDE.md section 9 with all 5 bugs. Seed git history per the script. Create the 5 fixture files in eval/fixtures/. Commit."

**Phase 3 — Models + state:**
> "Phase 3. Implement src/zeroops/models.py and src/zeroops/state.py exactly per CLAUDE.md section 7. Add pytest tests that validate a sample of each model. Commit."

**Phase 4 — Tools:**
> "Phase 4. Implement src/zeroops/tools/{code,git,repro,memory}.py per CLAUDE.md section 11. Manually test each tool against demo_repo and report the outputs. Commit."

**Phase 5 — Memory:**
> "Phase 5. Implement src/zeroops/memory/{store,embeddings}.py per CLAUDE.md section 10. Test: save an incident, search for it, verify retrieval. Commit."

**Phase 6 — Investigator:**
> "Phase 6. Implement the Investigator sub-graph in src/zeroops/agents/investigator.py. Each node loads its prompt from src/zeroops/prompts/ (prompts are in CLAUDE.md section 8 — write them to files now if not already). Each LLM call uses PydanticAI with the model from models.py. Test end-to-end on bug1_error.txt before claiming done. Commit."

**Phase 7 — Triage + Problem Manager + graph:**
> "Phase 7. Implement triage_node, problem_manager_node, and reporter_node per CLAUDE.md section 8 prompts. Assemble the full graph in src/zeroops/graph.py per section 12. Test end-to-end on all 5 bugs. Commit."

**Phase 8 — CLI runner:**
> "Phase 8. Implement src/zeroops/runner.py per CLAUDE.md section 13. Must stream each node's output as a rich Panel. Show me the output on bug1. Commit."

**Phase 9 — Benchmark:**
> "Phase 9. Implement eval/benchmark.py per CLAUDE.md section 14. Run it, show me the metrics table. Commit."

**Phase 10 — Frontend (stretch):**
> "Phase 10. Scaffold a minimal Next.js 14 App Router frontend in web/ that streams the agent's reasoning via SSE from a FastAPI backend at src/zeroops/server.py. Textarea input, three-panel layout: input / stream / final report. Commit."

---

## 19. Debugging principles

When something breaks:

1. **Read the error in full.** Paste it into your own reasoning before fixing.
2. **Check state shape first.** Most LangGraph bugs are state-shape mismatches. Print `state` at the start of the failing node.
3. **Check prompt loading.** If a node produces garbage, verify the prompt file was loaded correctly. Print the first 200 chars.
4. **Check structured output failures.** PydanticAI validation errors usually mean the model returned prose around the JSON. Strengthen the prompt's "Do not include prose outside the JSON" line.
5. **Isolate the failing node.** Run just that node with fake state to repro faster than re-running the whole graph.
6. **The Evaluator is the most load-bearing node.** If the loop never terminates or terminates too early, that's where to look.

7. **Retry policy for structured output failures.** Every PydanticAI call must have exactly 1 automatic retry on validation error. On retry, prepend a repair instruction: `"Your previous response failed validation. Return ONLY valid JSON matching the schema. Error: {validation_error}"`. If the retry also fails, raise the error clearly — do not silently fall back to unstructured text. This policy applies to all agent nodes uniformly.

8. **Windows-first development.** This project is built on Windows. Use `python -m module` everywhere (not bare script paths). Avoid `/tmp` in repro scripts — use `tempfile.mkdtemp()`. Use `pathlib.Path` for all file operations. Test all CLI commands in PowerShell.

---

## 20. Things to NOT do (common failure modes)

- Do not put prompts in Python strings. Put them in `.md` files.
- Do not make the agents separate projects. One graph, three agents.
- Do not skip the Evaluator loop. It's the thing that makes this an agent.
- Do not swap in OpenAI. Use Claude via `anthropic` SDK.
- Do not silently fall back to unstructured output. If PydanticAI validation fails, raise and retry — not swallow.
- Do not change the demo bug patterns. Bug 1 and Bug 2 sharing `incomplete_symbol_rename` is load-bearing for the demo.
- Do not run `run_repro` by default. `REPRO_EXECUTION_ENABLED=false` is the safe default.
- Do not build the frontend before the CLI works. Frontend is stretch.
- Do not skip the benchmark. Evaluation numbers in the README are a major differentiator.
- Do not write a README that reads like a student project. Use the Section 15 template which is written in senior-engineer voice.

---

## 21. If the user asks you something not covered here

Ask them directly. Do not guess. The user has thought carefully about this project and has a specific vision. When in doubt, quote the relevant CLAUDE.md section and ask for their decision.

Good luck. Build well. Ship before 9 AM April 21.