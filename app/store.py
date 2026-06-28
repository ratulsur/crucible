"""Session and user store.

In-memory: live session config (persona, voice, role, user).
SQLite: completed sessions + user accounts.
"""
from __future__ import annotations

import json
import sqlite3
import threading
import time
from dataclasses import dataclass, field


from .config import get_settings


@dataclass
class User:
    id: int
    username: str
    password_hash: str
    created_at: float


@dataclass
class SessionConfig:
    session_id: str
    role_target: str
    focus_areas: list[str]
    seniority: str
    persona_name: str
    persona_gender: str
    voice: str
    difficulty: str
    jd_text: str = ""
    user_id: int | None = None
    created_at: float = field(default_factory=time.time)


class SessionStore:
    def __init__(self) -> None:
        self._cfg: dict[str, SessionConfig] = {}
        self._lock = threading.Lock()
        self._init_db()

    # ------------------------------------------------------------------ #
    # In-memory session config
    # ------------------------------------------------------------------ #
    def put(self, cfg: SessionConfig) -> None:
        with self._lock:
            self._cfg[cfg.session_id] = cfg

    def get(self, session_id: str) -> SessionConfig | None:
        return self._cfg.get(session_id)

    # ------------------------------------------------------------------ #
    # SQLite helpers
    # ------------------------------------------------------------------ #
    def _conn(self) -> sqlite3.Connection:
        conn = sqlite3.connect(get_settings().db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def _init_db(self) -> None:
        with self._conn() as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS users (
                    id            INTEGER PRIMARY KEY AUTOINCREMENT,
                    username      TEXT UNIQUE NOT NULL,
                    password_hash TEXT NOT NULL,
                    created_at    REAL
                )
            """)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS sessions (
                    session_id     TEXT PRIMARY KEY,
                    user_id        INTEGER REFERENCES users(id),
                    created_at     REAL,
                    finished_at    REAL,
                    role_target    TEXT,
                    difficulty     TEXT,
                    persona_name   TEXT,
                    recommendation TEXT,
                    decision       TEXT,
                    transcript     TEXT,
                    evaluations    TEXT,
                    report         TEXT
                )
            """)
            # Migrate older databases that may be missing columns.
            existing = {row[1] for row in conn.execute("PRAGMA table_info(sessions)")}
            for col, defn in [
                ("user_id",  "INTEGER"),
                ("decision", "TEXT"),
            ]:
                if col not in existing:
                    conn.execute(f"ALTER TABLE sessions ADD COLUMN {col} {defn}")

    # ------------------------------------------------------------------ #
    # User accounts
    # ------------------------------------------------------------------ #
    def create_user(self, username: str, password_hash: str) -> User:
        now = time.time()
        with self._conn() as conn:
            cur = conn.execute(
                "INSERT INTO users (username, password_hash, created_at) VALUES (?,?,?)",
                (username, password_hash, now),
            )
            return User(id=cur.lastrowid, username=username,
                        password_hash=password_hash, created_at=now)

    def get_user_by_username(self, username: str) -> User | None:
        with self._conn() as conn:
            row = conn.execute(
                "SELECT id, username, password_hash, created_at FROM users WHERE username=?",
                (username,),
            ).fetchone()
        if not row:
            return None
        return User(**dict(row))

    # ------------------------------------------------------------------ #
    # Completed session records
    # ------------------------------------------------------------------ #
    def save_finished(self, cfg: SessionConfig, state: dict) -> None:
        report = state.get("report", {})
        with self._conn() as conn:
            conn.execute(
                """INSERT OR REPLACE INTO sessions
                   (session_id, user_id, created_at, finished_at, role_target,
                    difficulty, persona_name, recommendation, transcript,
                    evaluations, report)
                   VALUES (?,?,?,?,?,?,?,?,?,?,?)""",
                (
                    cfg.session_id,
                    cfg.user_id,
                    cfg.created_at,
                    time.time(),
                    cfg.role_target,
                    cfg.difficulty,
                    cfg.persona_name,
                    report.get("recommendation", ""),
                    json.dumps(state.get("transcript", [])),
                    json.dumps(state.get("evaluations", [])),
                    json.dumps(report),
                ),
            )

    def update_decision(self, session_id: str, decision: str) -> None:
        with self._conn() as conn:
            conn.execute(
                "UPDATE sessions SET decision=? WHERE session_id=?",
                (decision, session_id),
            )

    def list_user_sessions(self, user_id: int, limit: int = 50) -> list[dict]:
        with self._conn() as conn:
            rows = conn.execute(
                """SELECT session_id, created_at, finished_at, role_target,
                          difficulty, persona_name, recommendation, decision, report
                   FROM sessions WHERE user_id=?
                   ORDER BY finished_at DESC LIMIT ?""",
                (user_id, limit),
            ).fetchall()
        results = []
        for r in rows:
            d = dict(r)
            try:
                d["report"] = json.loads(d["report"] or "{}")
            except Exception:
                d["report"] = {}
            results.append(d)
        return results

    def list_recent(self, limit: int = 20) -> list[dict]:
        with self._conn() as conn:
            rows = conn.execute(
                """SELECT session_id, created_at, finished_at, role_target,
                          difficulty, persona_name, recommendation, decision
                   FROM sessions ORDER BY finished_at DESC LIMIT ?""",
                (limit,),
            ).fetchall()
        return [dict(r) for r in rows]


store = SessionStore()
