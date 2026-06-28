"""Pacing controller.

Deliberately deterministic — control flow should be predictable, not left to an
LLM. After each scored answer it decides two things:

  1. Whether to advance to the next phase. It allots a target number of questions
     per phase (scaled by difficulty), and advances when that's met. A very strong
     run can advance early; a shaky one can earn one extra question.
  2. When the interview should wrap.

The interviewer still phrases everything; pacing just moves the pointer.
"""
from __future__ import annotations

from ..state import PHASE_ORDER, InterviewState

# Base number of main questions per phase before advancing.
_BASE_BUDGET = {
    "intro": 1,
    "warmup": 1,
    "technical": 3,
    "system_design": 2,
    "behavioral": 2,
    "deep_dive": 2,
    "wrap": 1,
}

_DIFFICULTY_SCALE = {"easy": 0.8, "standard": 1.0, "hard": 1.2, "brutal": 1.3}


def _budget(phase: str, difficulty: str) -> int:
    scale = _DIFFICULTY_SCALE.get(difficulty, 1.0)
    return max(1, round(_BASE_BUDGET.get(phase, 1) * scale))


def _phase_question_count(state: InterviewState) -> int:
    """Count candidate answers recorded since the current phase began."""
    return state.get("_phase_q", 0)


def pacing_node(state: InterviewState) -> dict:
    phase = state.get("phase", "intro")
    difficulty = state.get("difficulty", "standard")
    evals = state.get("evaluations", [])
    last_overall = evals[-1]["overall"] if evals else 3

    phase_q = state.get("_phase_q", 0) + 1
    budget = _budget(phase, difficulty)

    # Strong answers can let us move on a touch early; weak ones earn a follow-up.
    advance = phase_q >= budget
    if last_overall >= 5 and phase_q >= max(1, budget - 1):
        advance = True
    if last_overall <= 2 and phase_q < budget + 1 and phase not in ("intro", "warmup"):
        advance = False

    updates: dict = {}
    if advance:
        order = [p.value for p in PHASE_ORDER]
        idx = order.index(phase) if phase in order else 0
        if idx + 1 < len(order):
            updates["phase"] = order[idx + 1]
            updates["_phase_q"] = 0
        else:
            updates["phase"] = "wrap"
            updates["_phase_q"] = 0
    else:
        updates["_phase_q"] = phase_q

    # Trigger a coding exercise once per session: after the first answer in the
    # technical or deep_dive phase, for non-easy difficulty, if not already done.
    already_coded = bool(state.get("code_evaluations")) or bool(
        state.get("coding_exercise_active")
    ) or bool(state.get("coding_problem"))
    coding_phase = phase in ("technical", "deep_dive")
    if (
        not already_coded
        and coding_phase
        and phase_q == 1
        and difficulty in ("standard", "hard", "brutal")
    ):
        updates["coding_exercise_active"] = True

    return updates
