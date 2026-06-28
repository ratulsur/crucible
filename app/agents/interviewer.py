"""Interviewer agent.

The face of the app. Given the conversation so far, the plan, the current phase,
and (after the first turn) the evaluator's read on the last answer, it produces
the next thing the interviewer says: an opening, a follow-up probe, or a
transition into the next phase. The persona lives in persona_system_prompt.
"""
from __future__ import annotations

from langchain_core.messages import AIMessage, HumanMessage, SystemMessage

from ..llm import get_llm
from ..persona import persona_system_prompt
from ..state import InterviewState


def _history_messages(transcript: list[dict]) -> list:
    msgs = []
    for turn in transcript:
        if turn["role"] == "interviewer":
            msgs.append(AIMessage(content=turn["text"]))
        else:
            msgs.append(HumanMessage(content=turn["text"]))
    return msgs


def interviewer_node(state: InterviewState) -> dict:
    transcript = state.get("transcript", [])
    phase = state.get("phase", "intro")
    plan = {p["phase"]: p for p in state.get("plan", [])}
    current = plan.get(phase, {"goal": "", "topics": []})

    # Answer evaluator hook — press on weak spots.
    evals = state.get("evaluations", [])
    hook = evals[-1].get("follow_up_hook", "") if evals else ""

    # Code reviewer hook — follow up on submitted code.
    code_evals = state.get("code_evaluations", [])
    code_hook = code_evals[-1].get("follow_up_thread", "") if code_evals else ""

    # Pacing signals a coding exercise. Only act on it if the problem hasn't
    # been presented yet (avoid re-presenting on subsequent turns).
    coding_active = (
        state.get("coding_exercise_active", False)
        and not state.get("coding_problem")
    )

    if not transcript:
        instruction = (
            "This is the very first thing you say. Greet the candidate warmly, "
            "introduce yourself in one sentence, then ask them to walk you through "
            "their background — the roles they have held, key projects they have "
            "built, and what drew them into generative AI. You want specifics: "
            "companies, timelines, what they actually built. Keep your opener to "
            "2-3 sentences and then let them talk."
        )
    elif code_hook:
        instruction = (
            f"The candidate just submitted a coding exercise. "
            f"Thread to press on: {code_hook} "
            "Acknowledge the submission briefly, then ask exactly one probing follow-up "
            "question about their code or approach. React naturally."
        )
    elif coding_active:
        topics = ", ".join(current.get("topics", []))
        instruction = (
            f"You are in the '{phase}' phase. Topics: {topics}. "
            "It's time to give the candidate a practical coding exercise. "
            "First react briefly to the conversation so far, then naturally transition "
            "to the exercise. Tell them they'll see a code editor appear. "
            "Choose a focused Python problem relevant to the current phase "
            "(e.g., implement a chunking function for RAG, write a simple retry "
            "decorator for an LLM call, build a token-budget checker, implement "
            "cosine similarity from scratch, etc.). Keep the problem scoped to "
            "10-20 minutes of work. "
            "At the very end of your response, on its own line, write exactly:\n"
            "CODING_EXERCISE: <the problem statement in 2-4 sentences>"
        )
    else:
        topics = ", ".join(current.get("topics", []))
        press = (
            f"There's a thread worth pulling: {hook} Press on that before moving on."
            if hook
            else "Decide whether to press the last answer once more or move forward."
        )
        instruction = (
            f"You are in the '{phase}' phase. Goal: {current.get('goal', '')}. "
            f"Topics in play: {topics}. {press} "
            "Ask exactly one question or follow-up. React to their last answer in a "
            "few words first, naturally. Cross-quiz when their answer is incomplete — "
            "ask 'why', 'how would that scale', or 'what breaks if you do that'."
        )

    llm = get_llm()
    # Anthropic requires at least one user message. Merge the turn instruction
    # into the system prompt, then seed with a HumanMessage when the transcript
    # is empty (first turn). On subsequent turns the transcript ends with a
    # candidate HumanMessage, so no seed is needed.
    full_system = persona_system_prompt(dict(state)) + "\n\n---\nFor this turn:\n" + instruction
    history = _history_messages(transcript)
    if not history:
        history = [HumanMessage(content="Please begin.")]
    messages = [SystemMessage(content=full_system)] + history
    resp = llm.invoke(messages)
    utterance = resp.content if isinstance(resp.content, str) else str(resp.content)
    utterance = utterance.strip()

    # Extract CODING_EXERCISE marker if present.
    coding_problem = ""
    if "CODING_EXERCISE:" in utterance:
        parts = utterance.split("CODING_EXERCISE:", 1)
        utterance = parts[0].strip()
        coding_problem = parts[1].strip()

    new_transcript = transcript + [{"role": "interviewer", "text": utterance}]
    updates: dict = {
        "interviewer_utterance": utterance,
        "last_question": utterance,
        "transcript": new_transcript,
        "question_count": state.get("question_count", 0) + 1,
    }
    if coding_problem:
        updates["coding_problem"] = coding_problem
        # Leave coding_exercise_active = True so main.py signals the frontend.
        # code_reviewer_node clears it once the candidate submits their code.
    return updates
