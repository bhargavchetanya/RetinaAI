"""RetinaAI inference API (FastAPI) with login and role-based access.

Run from the project root:
    python -m uvicorn backend.main:app --port 8000
Docs (auto-generated, try requests in the browser): http://localhost:8000/docs

Roles:  admin (all records, manage users) · hospital (its doctors' screenings, add doctors)
        doctor (screens patients, sees own screenings) · patient (own reports only)
"""
from __future__ import annotations

import base64
import sys
from contextlib import asynccontextmanager
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from fastapi import Depends, FastAPI, File, Form, Header, HTTPException, UploadFile  # noqa: E402
from fastapi.middleware.cors import CORSMiddleware  # noqa: E402
from fastapi.responses import Response  # noqa: E402
from pydantic import BaseModel, Field  # noqa: E402

from backend import auth, chatbot, db  # noqa: E402
from backend.report import IMG_DIR, build_pdf, save_images  # noqa: E402
from retina.config import (BASELINES_PATH, CHECKPOINT_PATH, CLUSTERING_PATH, DATA_SUMMARY_PATH,  # noqa: E402
                           METRICS_PATH)
from retina.utils import load_json  # noqa: E402

predictor = None
load_error = None
STAFF = ("admin", "hospital", "doctor")


@asynccontextmanager
async def lifespan(_app):
    _startup()
    yield


def _startup():
    global predictor, load_error
    db.init()
    auth.seed_demo_accounts()
    if not CHECKPOINT_PATH.exists():
        load_error = f"No trained model at {CHECKPOINT_PATH.relative_to(ROOT)} – run scripts/03_train.py first."
        print("WARNING:", load_error)
        return
    try:
        from retina.inference import DRPredictor

        predictor = DRPredictor()
        print(f"model loaded on {predictor.device} (T={predictor.temperature:.2f}, "
              f"referral threshold={predictor.threshold:.2f})")
    except Exception as e:  # pragma: no cover
        load_error = f"Failed to load model: {e}"
        print("ERROR:", load_error)


app = FastAPI(title="RetinaAI API", version="2.0.0", lifespan=lifespan,
              description="Explainable diabetic-retinopathy screening")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])


@app.get("/api/health")
def health():
    return {"status": "ok", "model_loaded": predictor is not None, "error": load_error,
            "device": str(predictor.device) if predictor else None,
            "model_version": predictor.version if predictor else None}


# ============================================================== auth ========
class LoginIn(BaseModel):
    username: str
    password: str


class RegisterIn(BaseModel):
    username: str = Field(min_length=3, max_length=40, pattern=r"^[A-Za-z0-9_.-]+$")
    password: str = Field(min_length=6, max_length=128)
    full_name: str = Field(min_length=2, max_length=80)
    age: int | None = Field(default=None, ge=0, le=120)
    sex: str | None = None


class UserIn(RegisterIn):
    role: str
    hospital_id: int | None = None


@app.post("/api/auth/login")
def login(body: LoginIn):
    token, user = auth.login(body.username, body.password)
    if not token:
        raise HTTPException(401, "Wrong username or password")
    return {"token": token, "user": user}


@app.post("/api/auth/register")
def register(body: RegisterIn):
    """Self-registration is only for patients."""
    if db.get_user_by_username(body.username):
        raise HTTPException(409, "That username is already taken")
    db.create_user(body.username, auth.hash_password(body.password), "patient", body.full_name,
                   age=body.age, sex=body.sex)
    token, user = auth.login(body.username, body.password)
    return {"token": token, "user": user}


@app.get("/api/auth/me")
def me(user: dict = Depends(auth.current_user)):
    return user


@app.post("/api/auth/logout")
def logout(authorization: str | None = Header(default=None)):
    if authorization and " " in authorization:
        db.delete_session(authorization.split(" ", 1)[1].strip())
    return {"ok": True}


# ============================================================= users ========
@app.get("/api/users")
def users(role: str | None = None, user: dict = Depends(auth.require("admin", "hospital"))):
    if user["role"] == "hospital":                       # a hospital only sees its own doctors
        return db.list_users(role="doctor", hospital_id=user["id"])
    return db.list_users(role=role)


@app.post("/api/users")
def create_user(body: UserIn, user: dict = Depends(auth.require("admin", "hospital"))):
    if body.role not in db.ROLES:
        raise HTTPException(400, "invalid role")
    hospital_id = body.hospital_id
    if user["role"] == "hospital":
        if body.role != "doctor":
            raise HTTPException(403, "A hospital can only add doctors")
        hospital_id = user["id"]
    if body.role == "doctor":
        h = db.get_user(hospital_id) if hospital_id else None
        if not h or h["role"] != "hospital":
            raise HTTPException(400, "A doctor must belong to a hospital")
    else:
        hospital_id = None
    if db.get_user_by_username(body.username):
        raise HTTPException(409, "That username is already taken")
    uid = db.create_user(body.username, auth.hash_password(body.password), body.role, body.full_name,
                         hospital_id, body.age, body.sex)
    return db.get_user(uid)


@app.delete("/api/users/{uid}")
def delete_user(uid: int, user: dict = Depends(auth.require("admin", "hospital"))):
    target = db.get_user(uid)
    if not target:
        raise HTTPException(404, "not found")
    if target["id"] == user["id"]:
        raise HTTPException(400, "You cannot delete your own account")
    if user["role"] == "hospital" and not (target["role"] == "doctor" and target["hospital_id"] == user["id"]):
        raise HTTPException(403, "A hospital can only remove its own doctors")
    db.delete_user(uid)
    return {"ok": True}


@app.get("/api/patients")
def patients(user: dict = Depends(auth.require(*STAFF))):
    """Registered patients – used by staff to link a screening to a patient account."""
    return [{k: p[k] for k in ("id", "username", "full_name", "age", "sex")} for p in db.list_users("patient")]


# ========================================================= screening ========
@app.post("/api/screen")
async def screen(file: UploadFile = File(...), patient_id: int | None = Form(None),
                 patient_name: str = Form(""), patient_age: int | None = Form(None),
                 patient_sex: str = Form(""), diabetes_years: float | None = Form(None), eye: str = Form(""),
                 centre: str = Form(""), save: bool = Form(True),
                 user: dict = Depends(auth.require("doctor"))):
    """Only doctors upload images and screen patients (hospital/admin only review)."""
    if predictor is None:
        raise HTTPException(503, load_error or "model not loaded")
    data = await file.read()
    if len(data) > 25 * 1024 * 1024:
        raise HTTPException(413, "Image larger than 25 MB")
    try:
        result = predictor.predict(data)
    except ValueError as e:
        raise HTTPException(400, f"Could not read the image: {e}")
    if save:
        if patient_id:
            p = db.get_user(patient_id)
            if not p or p["role"] != "patient":
                raise HTTPException(400, "Unknown patient account")
            patient_name = patient_name or p["full_name"]
            patient_age = patient_age if patient_age is not None else p["age"]
            patient_sex = patient_sex or (p["sex"] or "")
        doctor_id = user["id"]
        hospital_id = user["hospital_id"]          # the doctor's hospital
        if not centre.strip() and hospital_id:
            centre = (db.get_user(hospital_id) or {}).get("full_name", "")
        meta = dict(patient_name=patient_name.strip(), patient_age=patient_age, patient_sex=patient_sex,
                    diabetes_years=diabetes_years, eye=eye, centre=centre.strip(),
                    patient_id=patient_id, doctor_id=doctor_id, hospital_id=hospital_id)
        sid = db.insert(meta, result)
        save_images(sid, result["images"])
        result["id"] = sid
    return result


def _get_or_404(user, sid):
    s = db.get_for(user, sid)
    if not s:                                   # same answer for "missing" and "not yours"
        raise HTTPException(404, "Record not found")
    return s


@app.get("/api/screenings")
def screenings(limit: int = 500, user: dict = Depends(auth.current_user)):
    return db.list_for(user, limit)


@app.get("/api/screenings/{sid}")
def screening(sid: int, user: dict = Depends(auth.current_user)):
    s = _get_or_404(user, sid)
    images = {}
    for k in ("original", "enhanced", "heatmap"):
        f = IMG_DIR / f"{sid}_{k}.png"
        if f.exists():
            images[k] = "data:image/png;base64," + base64.b64encode(f.read_bytes()).decode()
    if "enhanced" not in images and "original" in images:
        images["enhanced"] = images["original"]
    s["result"]["images"] = images
    return s


class FollowUp(BaseModel):
    status: str


@app.patch("/api/screenings/{sid}/followup")
def followup(sid: int, body: FollowUp, user: dict = Depends(auth.require(*STAFF))):
    if body.status not in {"pending", "referred", "seen_by_doctor", "not_required", "lost"}:
        raise HTTPException(400, "invalid status")
    _get_or_404(user, sid)
    db.set_followup(sid, body.status)
    return {"ok": True}


@app.delete("/api/screenings/{sid}")
def delete(sid: int, user: dict = Depends(auth.require("admin"))):
    if not db.delete(sid):
        raise HTTPException(404, "Record not found")
    return {"ok": True}


@app.get("/api/stats")
def stats(user: dict = Depends(auth.current_user)):
    return db.stats_for(user)


@app.get("/api/report/{sid}")
def report(sid: int, user: dict = Depends(auth.current_user)):
    s = _get_or_404(user, sid)
    pdf = build_pdf(s)
    return Response(pdf, media_type="application/pdf",
                    headers={"Content-Disposition": f'inline; filename="retinaai_report_{sid}.pdf"'})


# ============================================================ public ========
@app.get("/api/model")
def model_info():
    return {
        "metrics": load_json(METRICS_PATH),
        "baselines": load_json(BASELINES_PATH),
        "clustering": load_json(CLUSTERING_PATH),
        "data": load_json(DATA_SUMMARY_PATH),
    }


class ChatIn(BaseModel):
    message: str = Field(max_length=500)


@app.post("/api/chat")
def chat(body: ChatIn, user: dict | None = Depends(auth.optional_user)):
    return chatbot.answer(body.message, user)
