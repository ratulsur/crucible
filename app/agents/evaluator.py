"""Evaluator agent.

After each candidate answer, score it against a fixed rubric and return strict
JSON (an AnswerEvaluation). It also records what a strong answer would have
covered and, optionally, the single best thread to press on next — which the
interviewer picks up. Structured output keeps this reliable across turns.
"""
from __future__ import annotations

from langchain_core.messages import HumanMessage, SystemMessage

from ..llm import get_fast_llm
from ..state import AnswerEvaluation, InterviewState

_SYS = """You are a rigorous technical evaluator scoring a candidate's answer in a
senior Generative AI interview. Score 1-5 on each rubric dimension (1 weak, 3
solid, 5 exceptional). Be honest and calibrated — most real answers land at 2-4.
List the key points a strong answer would have covered that were missing. If one
specific thread is worth pressing, put it in follow_up_hook; otherwise leave it
empty. Keep 'note' to one short line for the coach."""


def evaluator_node(state: InterviewState) -> dict:
    question = state.get("last_question", "")
    answer = state.get("candidate_answer", "")
    if not answer.strip():
        return {}  # nothing to score (e.g. opening turn)

    llm = get_fast_llm(temperature=0.2).with_structured_output(AnswerEvaluation)
    result: AnswerEvaluation = llm.invoke(
        [
            SystemMessage(content=_SYS),
            HumanMessage(
                content=f"QUESTION:\n{question}\n\nCANDIDATE ANSWER:\n{answer}"
            ),
        ]
    )

    transcript = state.get("transcript", [])
    transcript = transcript + [{"role": "candidate", "text": answer}]
    evals = state.get("evaluations", []) + [result.model_dump()]
    return {"transcript": transcript, "evaluations": evals, "candidate_answer": ""}
