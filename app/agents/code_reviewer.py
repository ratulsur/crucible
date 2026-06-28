"""Code reviewer agent.

Runs after the candidate submits a coding exercise. Reads the problem statement,
the submitted code, and its execution output, then produces a structured review
that the interviewer uses to ask follow-up questions.
"""
from __future__ import annotations

from langchain_core.messages import HumanMessage, SystemMessage

from ..llm import get_fast_llm
from ..state import CodeReview, InterviewState

_SYS = """You are a senior engineer reviewing a candidate's code submission in a
GenAI interview. You have the problem statement, their Python code, and the
execution output.

Score 1-5 on each dimension (1 poor, 3 solid, 5 exceptional):
- correctness: does it solve the problem correctly?
- approach: is the algorithm/design sensible and idiomatic?
- code_quality: readability, naming, structure, edge-case handling.

In what_worked, name 1-2 concrete things they did well.
In what_missed, name the most important gap or error (be specific).
In follow_up_thread, write ONE focused question the interviewer should ask to
probe the candidate's understanding more deeply — about a trade-off, an edge
case, or an alternative approach. Leave it empty if the code is near-perfect."""


def code_reviewer_node(state: InterviewState) -> dict:
    problem = state.get("coding_problem", "")
    code = state.get("code_submitted", "")
    output = state.get("code_output", "")

    llm = get_fast_llm(temperature=0.2).with_structured_output(CodeReview)
    result: CodeReview = llm.invoke(
        [
            SystemMessage(content=_SYS),
            HumanMessage(
                content=(
                    f"PROBLEM:\n{problem}\n\n"
                    f"CODE:\n```python\n{code}\n```\n\n"
                    f"EXECUTION OUTPUT:\n{output}"
                )
            ),
        ]
    )

    # Add the code submission to the transcript so the coach can see it.
    transcript = state.get("transcript", []) + [
        {
            "role": "candidate",
            "text": f"[Coding exercise submission]\n```python\n{code}\n```\nOutput: {output}",
        }
    ]
    code_evals = state.get("code_evaluations", []) + [result.model_dump()]
    return {
        "transcript": transcript,
        "code_evaluations": code_evals,
        "coding_exercise_active": False,
        "coding_problem": "",
    }
