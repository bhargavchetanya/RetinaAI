"""SQLite storage for screenings (no server needed – works offline)."""
from __future__ import annotations

import json
import sqlite3
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path

STORAGE = Path(__file__).resolve().parent / "storage"
STORAGE.mkdir(exist_ok=True)
DB_PATH = STORAGE / "screenings.db"

SCHEMA = """
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


@contextmanager
def conn():
    c = sqlite3.connect(DB_PATH)
    c.row_factory = sqlite3.Row
    try:
        yield c
        c.commit()
    finally:
        c.close()


def init():
    with conn() as c:
        c.executescript(SCHEMA)


def insert(meta: dict, result: dict) -> int:
    slim = {k: v for k, v in result.items() if k != "images"}
    with conn() as c:
        cur = c.execute(
            """INSERT INTO screenings (created_at, patient_name, patient_age, patient_sex, diabetes_years,
               eye, centre, grade, confidence, p_referable, refer, quality_ok, followup, result_json)
               VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            (datetime.now().isoformat(timespec="seconds"), meta.get("patient_name"), meta.get("patient_age"),
             meta.get("patient_sex"), meta.get("diabetes_years"), meta.get("eye"), meta.get("centre"),
             result["grade"], result["confidence"], result["p_referable"], int(result["refer"]),
             int(result["quality"]["ok"]), "pending" if result["refer"] else "not_required", json.dumps(slim)),
        )
        return int(cur.lastrowid)


def _row(r: sqlite3.Row, full: bool = False) -> dict:
    d = dict(r)
    res = json.loads(d.pop("result_json") or "{}")
    d["refer"], d["quality_ok"] = bool(d["refer"]), bool(d["quality_ok"])
    d["grade_name"] = res.get("grade_name")
    if full:
        d["result"] = res
    return d


def list_all(limit: int = 200) -> list[dict]:
    with conn() as c:
        rows = c.execute("SELECT * FROM screenings ORDER BY id DESC LIMIT ?", (limit,)).fetchall()
    return [_row(r) for r in rows]


def get(sid: int) -> dict | None:
    with conn() as c:
        r = c.execute("SELECT * FROM screenings WHERE id=?", (sid,)).fetchone()
    return _row(r, full=True) if r else None


def set_followup(sid: int, status: str) -> bool:
    with conn() as c:
        cur = c.execute("UPDATE screenings SET followup=? WHERE id=?", (status, sid))
        return cur.rowcount > 0


def delete(sid: int) -> bool:
    with conn() as c:
        return c.execute("DELETE FROM screenings WHERE id=?", (sid,)).rowcount > 0


def stats() -> dict:
    with conn() as c:
        total = c.execute("SELECT COUNT(*) FROM screenings").fetchone()[0]
        referred = c.execute("SELECT COUNT(*) FROM screenings WHERE refer=1").fetchone()[0]
        poor = c.execute("SELECT COUNT(*) FROM screenings WHERE quality_ok=0").fetchone()[0]
        by_grade = {r[0]: r[1] for r in c.execute("SELECT grade, COUNT(*) FROM screenings GROUP BY grade")}
        by_day = [dict(r) for r in c.execute(
            """SELECT substr(created_at,1,10) AS day, COUNT(*) AS screenings, SUM(refer) AS referrals
               FROM screenings GROUP BY day ORDER BY day DESC LIMIT 30""")][::-1]
        by_centre = [dict(r) for r in c.execute(
            """SELECT COALESCE(NULLIF(centre,''),'Unspecified') AS centre, COUNT(*) AS screenings,
               SUM(refer) AS referrals FROM screenings GROUP BY 1 ORDER BY 2 DESC""")]
        followup = {r[0]: r[1] for r in c.execute("SELECT followup, COUNT(*) FROM screenings GROUP BY followup")}
    return {
        "total": total, "referred": referred, "poor_quality": poor,
        "referral_rate": round(referred / total, 4) if total else 0.0,
        "by_grade": [by_grade.get(g, 0) for g in range(5)],
        "by_day": by_day, "by_centre": by_centre, "followup": followup,
    }
