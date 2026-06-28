"""JWT authentication and password hashing."""
from __future__ import annotations

import os
from datetime import datetime, timedelta, timezone

import bcrypt
from fastapi import Header, HTTPException
from jose import JWTError, jwt

SECRET_KEY = os.environ.get("SECRET_KEY", "crucible-dev-key-change-in-production")
ALGORITHM = "HS256"
TOKEN_EXPIRE_HOURS = 168  # 1 week


def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()


def verify_password(plain: str, hashed: str) -> bool:
    return bcrypt.checkpw(plain.encode(), hashed.encode())


def create_token(user_id: int, username: str) -> str:
    expire = datetime.now(timezone.utc) + timedelta(hours=TOKEN_EXPIRE_HOURS)
    return jwt.encode(
        {"sub": username, "uid": user_id, "exp": expire},
        SECRET_KEY,
        algorithm=ALGORITHM,
    )


def _decode(token: str) -> dict:
    try:
        return jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
    except JWTError as exc:
        raise HTTPException(status_code=401, detail="Invalid or expired token") from exc


def current_user(authorization: str | None = Header(default=None)) -> dict:
    """FastAPI dependency — validates JWT and returns {uid, sub}."""
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Not authenticated")
    return _decode(authorization.removeprefix("Bearer ").strip())
