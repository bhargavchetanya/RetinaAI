"""Authentication + role-based access control.

* Passwords are never stored: PBKDF2-HMAC-SHA256, 200 000 iterations, random
  16-byte salt per user (Python standard library, no extra dependencies).
* Login returns a random 256-bit session token (stored server-side, expires
  after 7 days). The browser sends it as `Authorization: Bearer <token>`.
* `require(...)` is a FastAPI dependency that rejects users whose role is not
  allowed for an endpoint (HTTP 403). Which *records* a user may see is decided
  by `db.scope_clause`.
"""
from __future__ import annotations

import hashlib
import hmac
import secrets
from datetime import datetime, timedelta

from fastapi import Depends, Header, HTTPException

from backend import db

ITERATIONS = 200_000
SESSION_DAYS = 7

DEMO_ACCOUNTS = [
    # username, password, role, full name
    ("admin", "admin123", "admin", "System Administrator"),
    ("hospital1", "hospital123", "hospital", "PHC Rampur"),
    ("doctor1", "doctor123", "doctor", "Dr. Anjali Sharma"),
    ("patient1", "patient123", "patient", "Ramesh Kumar"),
]


def hash_password(password: str) -> str:
    salt = secrets.token_bytes(16)
    dk = hashlib.pbkdf2_hmac("sha256", password.encode(), salt, ITERATIONS)
    return f"pbkdf2_sha256${ITERATIONS}${salt.hex()}${dk.hex()}"


def verify_password(password: str, stored: str) -> bool:
    try:
        _, it, salt, digest = stored.split("$")
        dk = hashlib.pbkdf2_hmac("sha256", password.encode(), bytes.fromhex(salt), int(it))
        return hmac.compare_digest(dk.hex(), digest)        # constant-time comparison
    except Exception:
        return False


def login(username: str, password: str):
    row = db.get_user_by_username(username)
    if not row or not verify_password(password, row["password_hash"]):
        return None, None
    token = secrets.token_urlsafe(32)
    expires = (datetime.now() + timedelta(days=SESSION_DAYS)).isoformat(timespec="seconds")
    db.create_session(token, row["id"], expires)
    return token, db.get_user(row["id"])


def seed_demo_accounts():
    """First start only: create one account per role so the app can be demoed."""
    if db.count_users():
        return
    ids = {}
    for username, pw, role, name in DEMO_ACCOUNTS:
        hospital_id = ids.get("hospital") if role == "doctor" else None
        extra = {"age": 54, "sex": "M"} if role == "patient" else {}
        ids[role] = db.create_user(username, hash_password(pw), role, name, hospital_id, **extra)
    print("Created demo accounts (change these passwords for real use):")
    for username, pw, role, _ in DEMO_ACCOUNTS:
        print(f"   {role:<9} {username:<10} / {pw}")


# ------------------------------------------------------------ dependencies --
def current_user(authorization: str | None = Header(default=None)) -> dict:
    if not authorization or not authorization.lower().startswith("bearer "):
        raise HTTPException(401, "Please log in")
    user = db.user_for_token(authorization.split(" ", 1)[1].strip())
    if not user:
        raise HTTPException(401, "Session expired – please log in again")
    return user


def optional_user(authorization: str | None = Header(default=None)) -> dict | None:
    try:
        return current_user(authorization)
    except HTTPException:
        return None


def require(*roles: str):
    def dep(user: dict = Depends(current_user)) -> dict:
        if user["role"] not in roles:
            raise HTTPException(403, f"This action needs one of these roles: {', '.join(roles)}")
        return user
    return dep
