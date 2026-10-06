"""SQLite storage: users, login sessions and screenings (no server needed – works offline).

Access rules (enforced by `scope_clause`):
  admin     – every record
  hospital  – records screened at that hospital (by the hospital or any of its doctors)
  doctor    – records the doctor screened
  patient   – only records linked to the patient's own account
"""
from __future__ import annotations

import json
import sqlite3
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path

STORAGE = Path(__file__).resolve().parent / "storage"
STORAGE.mkdir(exist_ok=True)
DB_PATH = STORAGE / "screenings.db"

ROLES = ("admin", "hospital", "doctor", "patient")

SCHEMA = """
CREATE TABLE IF NOT EXISTS users (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    username      TEXT UNIQUE NOT NULL COLLATE NOCASE,
    password_hash TEXT NOT NULL,
    role          TEXT NOT NULL CHECK (role IN ('admin','hospital','doctor','patient')),
    full_name     TEXT NOT NULL,
    hospital_id   INTEGER REFERENCES users(id),   -- for doctors: the hospital they work at
    age           INTEGER,
    sex           TEXT,
    created_at    TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS sessions (
    token      TEXT PRIMARY KEY,
    user_id    INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    expires_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS screenings (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    created_at    TEXT NOT NULL,
    patient_name  TEXT,
    patient_age   INTEGER,
    patient_sex   TEXT,
    diabetes_years REAL,
    eye           TEXT,
    centre        TEXT,
    grade         INTEGER,
    confidence    REAL,
    p_referable   REAL,
    refer         INTEGER,
    quality_ok    INTEGER,
    followup      TEXT DEFAULT 'pending',
    result_json   TEXT
);
"""

# columns added in v2 (role-based access) – migrated onto existing databases
NEW_SCREENING_COLUMNS = {"patient_id": "INTEGER", "doctor_id": "INTEGER", "hospital_id": "INTEGER"}


@contextmanager
def conn():
    c = sqlite3.connect(DB_PATH)
    c.row_factory = sqlite3.Row
    c.execute("PRAGMA foreign_keys = ON")
    try:
        yield c
        c.commit()
    finally:
        c.close()


def init():
    with conn() as c:
        c.executescript(SCHEMA)
        cols = {r["name"] for r in c.execute("PRAGMA table_info(screenings)")}
        for name, typ in NEW_SCREENING_COLUMNS.items():
            if name not in cols:
                c.execute(f"ALTER TABLE screenings ADD COLUMN {name} {typ}")


def now() -> str:
    return datetime.now().isoformat(timespec="seconds")


# ---------------------------------------------------------------- users ----
def create_user(username, password_hash, role, full_name, hospital_id=None, age=None, sex=None) -> int:
    with conn() as c:
        cur = c.execute(
            "INSERT INTO users (username, password_hash, role, full_name, hospital_id, age, sex, created_at)"
            " VALUES (?,?,?,?,?,?,?,?)",
            (username.strip(), password_hash, role, full_name.strip(), hospital_id, age, sex, now()))
        return int(cur.lastrowid)


def _user(r):
    if not r:
        return None
    d = dict(r)
    d.pop("password_hash", None)
    return d


def get_user_by_username(username):
    with conn() as c:
        return c.execute("SELECT * FROM users WHERE username = ?", (username.strip(),)).fetchone()


def get_user(uid):
    with conn() as c:
        return _user(c.execute("SELECT * FROM users WHERE id = ?", (uid,)).fetchone())


def list_users(role=None, hospital_id=None):
    q = ("SELECT u.*, h.full_name AS hospital_name FROM users u "
         "LEFT JOIN users h ON h.id = u.hospital_id WHERE 1=1")
    args = []
    if role:
        q += " AND u.role = ?"; args.append(role)
    if hospital_id is not None:
        q += " AND u.hospital_id = ?"; args.append(hospital_id)
    q += " ORDER BY u.role, u.full_name"
    with conn() as c:
        return [_user(r) for r in c.execute(q, args)]


def delete_user(uid) -> bool:
    with conn() as c:
        c.execute("DELETE FROM sessions WHERE user_id = ?", (uid,))
        c.execute("UPDATE users SET hospital_id = NULL WHERE hospital_id = ?", (uid,))
        return c.execute("DELETE FROM users WHERE id = ?", (uid,)).rowcount > 0


def count_users() -> int:
    with conn() as c:
        return c.execute("SELECT COUNT(*) FROM users").fetchone()[0]


# ------------------------------------------------------------- sessions ----
def create_session(token, user_id, expires_at):
    with conn() as c:
        c.execute("DELETE FROM sessions WHERE expires_at < ?", (now(),))
        c.execute("INSERT INTO sessions VALUES (?,?,?)", (token, user_id, expires_at))


def user_for_token(token):
    with conn() as c:
        r = c.execute("SELECT u.* FROM sessions s JOIN users u ON u.id = s.user_id "
                      "WHERE s.token = ? AND s.expires_at > ?", (token, now())).fetchone()
    return _user(r)


def delete_session(token):
    with conn() as c:
        c.execute("DELETE FROM sessions WHERE token = ?", (token,))


# ----------------------------------------------------------- screenings ----
def scope_clause(user: dict, alias: str = ""):
    """SQL WHERE fragment restricting screenings to what `user` may see."""
    p = f"{alias}." if alias else ""
    role = user["role"]
    if role == "admin":
        return "1=1", []
    if role == "hospital":
        return f"{p}hospital_id = ?", [user["id"]]
    if role == "doctor":
        return f"{p}doctor_id = ?", [user["id"]]
    return f"{p}patient_id = ?", [user["id"]]          # patient


def insert(meta: dict, result: dict) -> int:
    slim = {k: v for k, v in result.items() if k != "images"}
    with conn() as c:
        cur = c.execute(
            """INSERT INTO screenings (created_at, patient_name, patient_age, patient_sex, diabetes_years,
               eye, centre, grade, confidence, p_referable, refer, quality_ok, followup, result_json,
               patient_id, doctor_id, hospital_id)
               VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            (now(), meta.get("patient_name"), meta.get("patient_age"),
             meta.get("patient_sex"), meta.get("diabetes_years"), meta.get("eye"), meta.get("centre"),
             result["grade"], result["confidence"], result["p_referable"], int(result["refer"]),
             int(result["quality"]["ok"]), "pending" if result["refer"] else "not_required", json.dumps(slim),
             meta.get("patient_id"), meta.get("doctor_id"), meta.get("hospital_id")),
        )
        return int(cur.lastrowid)


_LIST_SQL = """SELECT s.*, d.full_name AS doctor_name, h.full_name AS hospital_name
               FROM screenings s
               LEFT JOIN users d ON d.id = s.doctor_id
               LEFT JOIN users h ON h.id = s.hospital_id"""


def _row(r: sqlite3.Row, full: bool = False) -> dict:
    d = dict(r)
    res = json.loads(d.pop("result_json") or "{}")
    d["refer"], d["quality_ok"] = bool(d["refer"]), bool(d["quality_ok"])
    d["grade_name"] = res.get("grade_name")
    if full:
        d["result"] = res
    return d


def list_for(user: dict, limit: int = 500) -> list[dict]:
    where, args = scope_clause(user, "s")
    with conn() as c:
        rows = c.execute(f"{_LIST_SQL} WHERE {where} ORDER BY s.id DESC LIMIT ?", (*args, limit)).fetchall()
    return [_row(r) for r in rows]


def get_for(user: dict, sid: int) -> dict | None:
    """Returns the record only if `user` is allowed to see it."""
    where, args = scope_clause(user, "s")
    with conn() as c:
        r = c.execute(f"{_LIST_SQL} WHERE s.id = ? AND {where}", (sid, *args)).fetchone()
    return _row(r, full=True) if r else None


def set_followup(sid: int, status: str) -> bool:
    with conn() as c:
        return c.execute("UPDATE screenings SET followup=? WHERE id=?", (status, sid)).rowcount > 0


def delete(sid: int) -> bool:
    with conn() as c:
        return c.execute("DELETE FROM screenings WHERE id=?", (sid,)).rowcount > 0


def stats_for(user: dict) -> dict:
    where, args = scope_clause(user)
    with conn() as c:
        q = lambda sql: c.execute(sql.replace("{W}", where), args)  # noqa: E731
        total = q("SELECT COUNT(*) FROM screenings WHERE {W}").fetchone()[0]
        referred = q("SELECT COUNT(*) FROM screenings WHERE refer=1 AND {W}").fetchone()[0]
        poor = q("SELECT COUNT(*) FROM screenings WHERE quality_ok=0 AND {W}").fetchone()[0]
        by_grade = {r[0]: r[1] for r in q("SELECT grade, COUNT(*) FROM screenings WHERE {W} GROUP BY grade")}
        by_day = [dict(r) for r in q(
            """SELECT substr(created_at,1,10) AS day, COUNT(*) AS screenings, SUM(refer) AS referrals
               FROM screenings WHERE {W} GROUP BY day ORDER BY day DESC LIMIT 30""")][::-1]
        by_centre = [dict(r) for r in q(
            """SELECT COALESCE(NULLIF(centre,''),'Unspecified') AS centre, COUNT(*) AS screenings,
               SUM(refer) AS referrals FROM screenings WHERE {W} GROUP BY 1 ORDER BY 2 DESC""")]
        followup = {r[0]: r[1] for r in q("SELECT followup, COUNT(*) FROM screenings WHERE {W} GROUP BY followup")}
    return {
        "total": total, "referred": referred, "poor_quality": poor,
        "referral_rate": round(referred / total, 4) if total else 0.0,
        "by_grade": [by_grade.get(g, 0) for g in range(5)],
        "by_day": by_day, "by_centre": by_centre, "followup": followup,
    }
