# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Commands

```bash
# From the Crucible/ directory
python -m venv .venv && source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt

cp .env.example .env   # fill in ANTHROPIC_API_KEY and/or OPENAI_API_KEY

uvicorn app.main:app --reload   # dev server at http://localhost:8000
```

No test suite, linter config, or build step is defined. The app runs directly via Uvicorn.

## Architecture

The app is a FastAPI backend (`app/main.py`) that drives a LangGraph multi-agent interview system. The graph is compiled once (`graph.py`:`get_graph()`, `@lru_cache`) and invoked **once per API turn**, with a `MemorySaver` checkpointer persisting state between calls via `session_id` as the thread key.

### Turn routing (`graph.py`)

The entry edge dispatches on `InterviewState.turn_type`:

| `turn_type` | Path |
|---|---|
| `"start"` | `strategist → interviewer` |
| `"answer"` | `evaluator → pacing → interviewer` |
| `"wrap"` | `coach` |

### Agents (`app/agents/`)

- **strategist** — runs once at start; produces a `plan: list[dict]` (phase + goal + topics) from role/focus areas.
- **interviewer** — the only agent the candidate hears; reads `evaluator.follow_up_hook` to press on weak spots; never breaks character.
- **evaluator** — scores each answer 1–5 across five rubric dimensions; returns `AnswerEvaluation` via `.with_structured_output()`.
- **pacing** — deterministic, no LLM; owns phase advancement logic using per-phase question budgets scaled by `difficulty`.
- **coach** — runs once at wrap; reads full transcript + all evaluations; produces `FeedbackReport` via `.with_structured_output()`.

### State (`app/state.py`)

`InterviewState` (TypedDict) is the single source of truth. Agents return partial dicts that LangGraph merges. Structured agent outputs (`AnswerEvaluation`, `FeedbackReport`) are Pydantic models serialized to `evaluations: list[dict]` and `report: dict` in state.

To add a phase: extend `Phase` enum and `PHASE_ORDER` in `state.py`, then add a budget entry in `pacing.py`.  
To change the scoring rubric: edit `AnswerEvaluation` fields in `state.py`.  
To add an agent: add a node function in `agents/`, register it in `graph.py`.

### LLM provider (`app/llm.py`)

`get_llm(temperature?)` is an `@lru_cache` factory. Provider selection order: `LLM_PROVIDER` env var → `auto` prefers Anthropic if `ANTHROPIC_API_KEY` is set, falls back to OpenAI. All agents call `get_llm()` so swapping providers requires no agent changes.

### Key env vars

| Variable | Purpose |
|---|---|
| `ANTHROPIC_API_KEY` | Agent LLM (preferred) |
| `OPENAI_API_KEY` | Audio STT/TTS; LLM fallback |
| `LLM_PROVIDER` | `auto` \| `anthropic` \| `openai` |
| `ANTHROPIC_MODEL` | Default `claude-sonnet-4-6` |
| `CRUCIBLE_ACCESS_TOKEN` | Optional `x-access-token` API gate |

Audio (STT/TTS) requires `OPENAI_API_KEY`; without it the web client falls back to browser speech APIs.

### Persistence

- **In-memory** (`MemorySaver`): live interview state; resets on process restart.
- **SQLite** (`app/store.py`, default `crucible.db`): completed session records only.

Single-user by design. For multi-replica use, swap `MemorySaver` for a persistent LangGraph checkpointer.
