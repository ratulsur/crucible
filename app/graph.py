"""The interview graph.

One graph, invoked once per turn. A checkpointer persists state per session
(thread_id), so each call resumes the same interview. The entry router dispatches
on `turn_type`:

    start  -> strategist -> interviewer            (plan the arc, ask opening Q)
    answer -> evaluator  -> pacing -> interviewer   (score, move pointer, ask next)
    wrap   -> coach                                 (write the final report)

Pacing is deterministic; the interviewer phrases everything the candidate hears.
"""
from __future__ import annotations

from functools import lru_cache

from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import END, START, StateGraph

from .agents.coach import coach_node
from .agents.code_reviewer import code_reviewer_node
from .agents.evaluator import evaluator_node
from .agents.interviewer import interviewer_node
from .agents.pacing import pacing_node
from .agents.strategist import strategist_node
from .state import InterviewState


def _route_entry(state: InterviewState) -> str:
    turn = state.get("turn_type", "start")
    if turn == "start":
        return "strategist"
    if turn == "wrap":
        return "coach"
    if turn == "code":
        return "code_reviewer"
    return "evaluator"


@lru_cache
def get_graph():
    g = StateGraph(InterviewState)

    g.add_node("strategist", strategist_node)
    g.add_node("interviewer", interviewer_node)
    g.add_node("evaluator", evaluator_node)
    g.add_node("pacing", pacing_node)
    g.add_node("coach", coach_node)
    g.add_node("code_reviewer", code_reviewer_node)

    g.add_conditional_edges(
        START,
        _route_entry,
        {
            "strategist": "strategist",
            "evaluator": "evaluator",
            "coach": "coach",
            "code_reviewer": "code_reviewer",
        },
    )
    g.add_edge("strategist", "interviewer")
    g.add_edge("evaluator", "pacing")
    g.add_edge("pacing", "interviewer")
    g.add_edge("code_reviewer", "interviewer")
    g.add_edge("interviewer", END)
    g.add_edge("coach", END)

    return g.compile(checkpointer=MemorySaver())
