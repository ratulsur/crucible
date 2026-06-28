"""Crucible — FastAPI application."""
from __future__ import annotations

import os
import subprocess
import sys
import tempfile
import uuid

from fastapi import Depends, FastAPI, File, Header, HTTPException, UploadFile
from fastapi.responses import FileResponse, Response
from fastapi.staticfiles import StaticFiles
from pathlib import Path

from .audio import AudioUnavailable, synthesize, transcribe
from .auth import create_token, current_user, hash_password, verify_password
from .config import get_settings
from .graph import get_graph
from .persona import voice_for
from .schemas import (
    AnswerRequest,
    CodeRequest,
    DecisionRequest,
    EndRequest,
    LoginRequest,
    RegisterRequest,
    RunCodeRequest,
    StartRequest,
    TokenResponse,
    TTSRequest,
    TurnResponse,
)
from .store import SessionConfig, store

WEB_DIR = Path(__file__).resolve().parent.parent / "web"

app = FastAPI(title="Crucible", version="2.0.0")


# --------------------------------------------------------------------------- #
# Helpers
# --------------------------------------------------------------------------- #
def _config(session_id: str) -> SessionConfig:
    cfg = store.get(session_id)
    if not cfg:
        raise HTTPException(status_code=404, detail="Unknown session")
    return cfg


def _run_turn(session_id: str, inputs: dict) -> dict:
    graph = get_graph()
    return graph.invoke(inputs, config={"configurable": {"thread_id": session_id}})


def _execute_code(code: str, timeout: int = 30) -> str:
    with tempfile.NamedTemporaryFile(
        mode="w", suffix=".py", delete=False, encoding="utf-8"
    ) as f:
        f.write(code)
        fname = f.name
    try:
        result = subprocess.run(
            [sys.executable, fname],
            capture_output=True,
            text=True,
            timeout=timeout,
        )
        out = result.stdout
        if result.stderr:
            out += ("\n" if out else "") + "[stderr]\n" + result.stderr
        return out.strip() or "(no output)"
    except subprocess.TimeoutExpired:
        return f"[Error: execution timed out after {timeout}s]"
    except Exception as e:
        return f"[Error: {e}]"
    finally:
        try:
            os.unlink(fname)
        except OSError:
            pass


# --------------------------------------------------------------------------- #
# Auth
# --------------------------------------------------------------------------- #
@app.post("/api/auth/register", response_model=TokenResponse)
def register(req: RegisterRequest) -> TokenResponse:
    if len(req.username.strip()) < 3:
        raise HTTPException(status_code=400, detail="Username must be at least 3 characters")
    if len(req.password) < 6:
        raise HTTPException(status_code=400, detail="Password must be at least 6 characters")
    existing = store.get_user_by_username(req.username.strip())
    if existing:
        raise HTTPException(status_code=409, detail="Username already taken")
    user = store.create_user(req.username.strip(), hash_password(req.password))
    token = create_token(user.id, user.username)
    return TokenResponse(access_token=token, username=user.username, user_id=user.id)


@app.post("/api/auth/login", response_model=TokenResponse)
def login(req: LoginRequest) -> TokenResponse:
    user = store.get_user_by_username(req.username.strip())
    if not user or not verify_password(req.password, user.password_hash):
        raise HTTPException(status_code=401, detail="Invalid username or password")
    token = create_token(user.id, user.username)
    return TokenResponse(access_token=token, username=user.username, user_id=user.id)


# --------------------------------------------------------------------------- #
# Interview turns
# --------------------------------------------------------------------------- #
@app.post("/api/session/start", response_model=TurnResponse)
def start_session(
    req: StartRequest, user: dict = Depends(current_user)
) -> TurnResponse:
    session_id = uuid.uuid4().hex
    name = req.persona_name or (
        "Anjali Mehta" if req.persona_gender == "female" else "Arjun Rao"
    )
    voice = voice_for(req.persona_gender, req.voice)
    cfg = SessionConfig(
        session_id=session_id,
        role_target=req.role_target,
        focus_areas=req.focus_areas,
        seniority=req.seniority,
        persona_name=name,
        persona_gender=req.persona_gender,
        voice=voice,
        difficulty=req.difficulty,
        jd_text=req.jd_text or "",
        user_id=user["uid"],
    )
    store.put(cfg)

    state = _run_turn(
        session_id,
        {
            "session_id": session_id,
            "turn_type": "start",
            "role_target": req.role_target,
            "focus_areas": req.focus_areas,
            "seniority": req.seniority,
            "persona_name": name,
            "persona_gender": req.persona_gender,
            "difficulty": req.difficulty,
            "jd_text": req.jd_text or "",
            "phase": "intro",
            "question_count": 0,
            "_phase_q": 0,
            "transcript": [],
            "evaluations": [],
            "code_evaluations": [],
        },
    )
    return TurnResponse(
        session_id=session_id,
        utterance=state["interviewer_utterance"],
        phase=state.get("phase", "intro"),
        question_count=state.get("question_count", 1),
        voice=voice,
    )


@app.post("/api/session/answer", response_model=TurnResponse)
def answer(
    req: AnswerRequest, user: dict = Depends(current_user)
) -> TurnResponse:
    cfg = _config(req.session_id)
    if not req.answer.strip():
        raise HTTPException(status_code=400, detail="Empty answer")
    state = _run_turn(
        req.session_id,
        {"turn_type": "answer", "candidate_answer": req.answer},
    )
    return TurnResponse(
        session_id=req.session_id,
        utterance=state["interviewer_utterance"],
        phase=state.get("phase", "technical"),
        question_count=state.get("question_count", 0),
        voice=cfg.voice,
        coding_exercise=bool(state.get("coding_exercise_active") and state.get("coding_problem")),
        coding_problem=state.get("coding_problem", ""),
    )


@app.post("/api/run_code")
def run_code(
    req: RunCodeRequest, user: dict = Depends(current_user)
) -> dict:
    return {"output": _execute_code(req.code)}


@app.post("/api/session/code", response_model=TurnResponse)
def submit_code(
    req: CodeRequest, user: dict = Depends(current_user)
) -> TurnResponse:
    cfg = _config(req.session_id)
    if not req.code.strip():
        raise HTTPException(status_code=400, detail="Empty code submission")
    output = _execute_code(req.code)
    state = _run_turn(
        req.session_id,
        {"turn_type": "code", "code_submitted": req.code, "code_output": output},
    )
    return TurnResponse(
        session_id=req.session_id,
        utterance=state["interviewer_utterance"],
        phase=state.get("phase", "technical"),
        question_count=state.get("question_count", 0),
        voice=cfg.voice,
    )


@app.post("/api/session/end")
def end_session(
    req: EndRequest, user: dict = Depends(current_user)
) -> dict:
    cfg = _config(req.session_id)
    state = _run_turn(req.session_id, {"turn_type": "wrap"})
    store.save_finished(cfg, state)
    return {"session_id": req.session_id, "report": state.get("report", {})}


@app.patch("/api/sessions/{session_id}/decision")
def set_decision(
    session_id: str,
    req: DecisionRequest,
    user: dict = Depends(current_user),
) -> dict:
    store.update_decision(session_id, req.decision)
    return {"session_id": session_id, "decision": req.decision}


# --------------------------------------------------------------------------- #
# Audio
# --------------------------------------------------------------------------- #
@app.post("/api/stt")
async def stt(
    file: UploadFile = File(...), user: dict = Depends(current_user)
) -> dict:
    try:
        data = await file.read()
        text = transcribe(data, filename=file.filename or "answer.webm")
        return {"text": text}
    except AudioUnavailable as e:
        raise HTTPException(status_code=503, detail=str(e))


@app.post("/api/tts")
def tts(
    req: TTSRequest, user: dict = Depends(current_user)
) -> Response:
    try:
        audio = synthesize(req.text, req.voice)
        return Response(content=audio, media_type="audio/mpeg")
    except AudioUnavailable as e:
        raise HTTPException(status_code=503, detail=str(e))


# --------------------------------------------------------------------------- #
# Records & meta
# --------------------------------------------------------------------------- #
@app.get("/api/sessions")
def sessions(user: dict = Depends(current_user)) -> dict:
    return {"sessions": store.list_user_sessions(user["uid"])}


@app.get("/api/health")
def health() -> dict:
    s = get_settings()
    provider = "none"
    try:
        provider = s.resolved_llm_provider()
    except RuntimeError:
        pass
    return {
        "status": "ok",
        "llm_provider": provider,
        "audio_enabled": s.audio_enabled(),
    }


# --------------------------------------------------------------------------- #
# Web pages
# --------------------------------------------------------------------------- #
@app.get("/")
def index() -> FileResponse:
    return FileResponse(WEB_DIR / "index.html")


@app.get("/login")
def login_page() -> FileResponse:
    return FileResponse(WEB_DIR / "login.html")


@app.get("/dashboard")
def dashboard_page() -> FileResponse:
    return FileResponse(WEB_DIR / "dashboard.html")


app.mount("/web", StaticFiles(directory=str(WEB_DIR)), name="web")
