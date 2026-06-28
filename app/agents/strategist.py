"""Strategist agent.

Runs once at the start. Looks at the target role and the focus areas the
candidate picked, then lays out the interview arc: which phases to run and what
to probe in each. The interviewer reads this plan to stay on track.
"""
from __future__ import annotations

import json

from langchain_core.messages import HumanMessage, SystemMessage
from pydantic import BaseModel, Field

from ..llm import get_llm
from ..state import PHASE_ORDER, InterviewState


class PhasePlan(BaseModel):
    phase: str
    goal: str
    topics: list[str] = Field(default_factory=list)


class InterviewPlan(BaseModel):
    plan: list[PhasePlan]


_SYS = """You are a hiring strategist for senior Generative AI roles. Given a
target role and focus areas, design a tight interview plan.

Use exactly these phases in this order: {phases}.
For each phase give a one-line goal and 2-4 specific topics or scenarios tuned to
the role and focus areas. Be concrete and current (RAG, agents, evals,
fine-tuning, inference cost, safety, latency, vector stores, LLMOps, etc.).
The 'wrap' phase goal is to let the candidate ask questions and close warmly.

If a job description is provided, extract the key technical requirements and
weight the plan toward those competencies. If no JD is given, design a
well-rounded plan covering what top companies most commonly assess at
mid-to-senior level: LLM fundamentals, RAG architecture, agent design,
evaluation rigor, fine-tuning trade-offs, inference optimization, and
system design at scale."""


def strategist_node(state: InterviewState) -> dict:
    role = state.get("role_target", "Generative AI Engineer")
    focus = ", ".join(state.get("focus_areas") or []) or "general GenAI engineering"
    phases = ", ".join(p.value for p in PHASE_ORDER)
    jd_text = state.get("jd_text", "").strip()

    human_content = (
        f"Role: {role}\nSeniority: {state.get('seniority', 'senior')}\n"
        f"Focus areas: {focus}\nDifficulty: {state.get('difficulty', 'standard')}"
    )
    if jd_text:
        human_content += f"\n\nJob Description:\n{jd_text}"

    llm = get_llm(temperature=0.4).with_structured_output(InterviewPlan)
    result: InterviewPlan = llm.invoke(
        [
            SystemMessage(content=_SYS.format(phases=phases)),
            HumanMessage(content=human_content),
        ]
    )
    plan = [p.model_dump() for p in result.plan]
    return {"plan": plan, "phase": plan[0]["phase"] if plan else "intro"}
