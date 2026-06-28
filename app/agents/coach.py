"""Coach agent.

Runs once when the interview ends. Reads the full transcript and every per-answer
evaluation, then writes a structured FeedbackReport: a recommendation, competency
scores, strengths, gaps, specific action items, and model answers for the
weakest moments. The closing note is written in the interviewer's warm voice.
"""
from __future__ import annotations

import json

from langchain_core.messages import HumanMessage, SystemMessage

from ..llm import get_llm
from ..state import FeedbackReport, InterviewState

_SYS = """You are the interviewer, now writing up your honest assessment after a
senior Generative AI interview. You were warm but pressing throughout; your report
is candid, specific, and constructive.

Ground every judgement in what the candidate actually said. Pick competencies that
fit how the conversation went (e.g. RAG & retrieval, agents & orchestration,
evaluation & rigor, fine-tuning, systems & cost, communication). For the 2-3
weakest answers, write a model answer showing what a strong response covers.
Action items must be concrete and practiceable, not generic. The closing note is
a short, warm, direct message to the candidate in your own voice."""


def coach_node(state: InterviewState) -> dict:
    transcript = state.get("transcript", [])
    evals = state.get("evaluations", [])
    convo = "\n".join(
        f"{t['role'].upper()}: {t['text']}" for t in transcript
    )
    scores = json.dumps(evals, indent=2)

    llm = get_llm(temperature=0.4).with_structured_output(FeedbackReport)
    result: FeedbackReport = llm.invoke(
        [
            SystemMessage(content=_SYS),
            HumanMessage(
                content=f"ROLE: {state.get('role_target','GenAI Engineer')}\n"
                f"DIFFICULTY: {state.get('difficulty','standard')}\n\n"
                f"TRANSCRIPT:\n{convo}\n\nPER-ANSWER SCORES:\n{scores}"
            ),
        ]
    )
    return {"report": result.model_dump(), "phase": "done", "done": True}
