"""State container and the structured shapes the agents read and write.

The interview state is the single source of truth that flows through the
LangGraph. Agents return partial updates to it. Structured outputs (the
evaluator's rubric scores, the coach's report) are Pydantic models so the LLM is
forced to return well-typed JSON rather than prose we then have to parse.
"""
from __future__ import annotations

from enum import Enum
from typing import Annotated, Any, Literal, TypedDict

from pydantic import BaseModel, Field


# --- Interview phases (the arc the strategist lays out) ---
class Phase(str, Enum):
    INTRO = "intro"
    WARMUP = "warmup"
    TECHNICAL = "technical"
    SYSTEM_DESIGN = "system_design"
    BEHAVIORAL = "behavioral"
    DEEP_DIVE = "deep_dive"
    WRAP = "wrap"
    DONE = "done"


PHASE_ORDER: list[Phase] = [
    Phase.INTRO,
    Phase.WARMUP,
    Phase.TECHNICAL,
    Phase.SYSTEM_DESIGN,
    Phase.BEHAVIORAL,
    Phase.DEEP_DIVE,
    Phase.WRAP,
]


# --- Structured agent outputs ---
class AnswerEvaluation(BaseModel):
    """How a single candidate answer scored. Produced by the evaluator agent."""

    technical_accuracy: int = Field(ge=1, le=5, description="Correctness and rigor.")
    depth: int = Field(ge=1, le=5, description="Went beyond surface level.")
    structure: int = Field(ge=1, le=5, description="Organized, easy to follow.")
    communication: int = Field(ge=1, le=5, description="Clear, concise, confident.")
    evidence: int = Field(
        ge=1, le=5, description="Concrete examples, numbers, trade-offs."
    )
    overall: int = Field(ge=1, le=5, description="Holistic score for this answer.")
    missed_points: list[str] = Field(
        default_factory=list, description="Key things a strong answer would cover."
    )
    follow_up_hook: str = Field(
        default="",
        description="One specific thing worth pressing on next, if any.",
    )
    note: str = Field(default="", description="One-line internal note for the coach.")


class CompetencyScore(BaseModel):
    name: str
    score: int = Field(ge=1, le=5)
    comment: str


class ModelAnswer(BaseModel):
    question: str
    what_was_missing: str
    strong_answer: str


class FeedbackReport(BaseModel):
    """Final report produced by the coach agent."""

    recommendation: Literal[
        "strong_hire", "hire", "lean_hire", "lean_no_hire", "no_hire"
    ]
    headline: str = Field(description="One-sentence verdict.")
    competencies: list[CompetencyScore]
    strengths: list[str]
    gaps: list[str]
    action_items: list[str] = Field(
        description="Concrete, specific things to practice before the next round."
    )
    model_answers: list[ModelAnswer] = Field(default_factory=list)
    closing_note: str = Field(description="A warm, direct note from the interviewer.")


# --- The graph state ---
def _keep_last(_old: Any, new: Any) -> Any:
    return new


class Turn(TypedDict):
    role: Literal["interviewer", "candidate"]
    text: str


class CodeReview(BaseModel):
    """Code review produced by the code_reviewer agent."""

    correctness: int = Field(ge=1, le=5)
    approach: int = Field(ge=1, le=5)
    code_quality: int = Field(ge=1, le=5)
    overall: int = Field(ge=1, le=5)
    what_worked: str
    what_missed: str
    follow_up_thread: str = Field(
        default="", description="Specific thing the interviewer should press on."
    )


class InterviewState(TypedDict, total=False):
    # identity / setup
    session_id: str
    role_target: str
    focus_areas: list[str]
    seniority: str
    persona_name: str
    persona_gender: Literal["male", "female"]
    difficulty: str  # easy | standard | hard | brutal
    jd_text: str  # optional pasted job description

    # control
    turn_type: Literal["start", "answer", "wrap", "code"]
    phase: str
    question_count: int
    _phase_q: int  # answers recorded in the current phase (pacing controller)
    plan: list[dict]  # [{phase, goal, topics:[...]}]
    transcript: list[Turn]

    # per-turn payloads
    candidate_answer: str
    last_question: str
    interviewer_utterance: str

    # coding exercise
    coding_exercise_active: bool  # pacing sets this to trigger a coding turn
    coding_problem: str  # problem statement set by the interviewer
    code_submitted: str  # candidate's submitted code
    code_output: str  # execution result
    code_evaluations: list[dict]  # serialized CodeReview per coding exercise

    # accumulated analysis
    evaluations: list[dict]  # serialized AnswerEvaluation per answered question
    report: dict  # serialized FeedbackReport once the coach runs
    done: bool
