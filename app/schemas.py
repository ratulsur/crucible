"""Request and response shapes for the HTTP API."""
from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field


class RegisterRequest(BaseModel):
    username: str
    password: str


class LoginRequest(BaseModel):
    username: str
    password: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    username: str
    user_id: int


class DecisionRequest(BaseModel):
    decision: Literal["next_round", "rejected"]


class StartRequest(BaseModel):
    role_target: str = "Generative AI Engineer"
    focus_areas: list[str] = Field(default_factory=list)
    seniority: str = "senior"
    persona_gender: Literal["male", "female"] = "female"
    persona_name: str | None = None
    voice: str | None = None
    difficulty: Literal["easy", "standard", "hard", "brutal"] = "standard"
    jd_text: str | None = None


class TurnResponse(BaseModel):
    session_id: str
    utterance: str
    phase: str
    question_count: int
    voice: str
    done: bool = False
    coding_exercise: bool = False
    coding_problem: str = ""


class AnswerRequest(BaseModel):
    session_id: str
    answer: str


class CodeRequest(BaseModel):
    session_id: str
    code: str
    language: str = "python"


class RunCodeRequest(BaseModel):
    code: str
    language: str = "python"


class TTSRequest(BaseModel):
    text: str
    voice: str = "sage"


class EndRequest(BaseModel):
    session_id: str
