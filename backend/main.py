"""RetinaAI inference API (FastAPI).

Run from the project root:
    uvicorn backend.main:app --reload --port 8000
Docs (auto-generated, try requests in the browser): http://localhost:8000/docs
"""
from __future__ import annotations

import sys
from contextlib import asynccontextmanager
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from fastapi import FastAPI, File, Form, HTTPException, UploadFile  # noqa: E402
from fastapi.middleware.cors import CORSMiddleware  # noqa: E402
from fastapi.responses import Response  # noqa: E402
from pydantic import BaseModel  # noqa: E402

from backend import db  # noqa: E402
from backend.report import build_pdf, save_images  # noqa: E402
from retina.config import (BASELINES_PATH, CHECKPOINT_PATH, CLUSTERING_PATH, DATA_SUMMARY_PATH,  # noqa: E402
                           METRICS_PATH)
from retina.utils import load_json  # noqa: E402

predictor = None
load_error = None


@asynccontextmanager
async def lifespan(_app):
    _startup()
    yield


def _startup():
    global predictor, load_error
    db.init()
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


app = FastAPI(title="RetinaAI API", version="1.0.0", lifespan=lifespan,
              description="Explainable diabetic-retinopathy screening")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])


@app.get("/api/health")
def health():
    return {"status": "ok", "model_loaded": predictor is not None, "error": load_error,
            "device": str(predictor.device) if predictor else None,
            "model_version": predictor.version if predictor else None}


@app.post("/api/screen")
async def screen(file: UploadFile = File(...), patient_name: str = Form(""), patient_age: int | None = Form(None),
                 patient_sex: str = Form(""), diabetes_years: float | None = Form(None), eye: str = Form(""),
                 centre: str = Form(""), save: bool = Form(True)):
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
        meta = dict(patient_name=patient_name.strip(), patient_age=patient_age, patient_sex=patient_sex,
                    diabetes_years=diabetes_years, eye=eye, centre=centre.strip())
        sid = db.insert(meta, result)
        save_images(sid, result["images"])
        result["id"] = sid
    return result


@app.get("/api/screenings")
def screenings(limit: int = 200):
    return db.list_all(limit)


@app.get("/api/screenings/{sid}")
def screening(sid: int):
    s = db.get(sid)
    if not s:
        raise HTTPException(404, "not found")
    return s


class FollowUp(BaseModel):
    status: str


@app.patch("/api/screenings/{sid}/followup")
def followup(sid: int, body: FollowUp):
    if body.status not in {"pending", "referred", "seen_by_doctor", "not_required", "lost"}:
        raise HTTPException(400, "invalid status")
    if not db.set_followup(sid, body.status):
        raise HTTPException(404, "not found")
    return {"ok": True}


@app.delete("/api/screenings/{sid}")
def delete(sid: int):
    if not db.delete(sid):
        raise HTTPException(404, "not found")
    return {"ok": True}


@app.get("/api/stats")
def stats():
    return db.stats()


@app.get("/api/report/{sid}")
def report(sid: int):
    s = db.get(sid)
    if not s:
        raise HTTPException(404, "not found")
    pdf = build_pdf(s)
    return Response(pdf, media_type="application/pdf",
                    headers={"Content-Disposition": f'inline; filename="retinaai_report_{sid}.pdf"'})


@app.get("/api/model")
def model_info():
    return {
        "metrics": load_json(METRICS_PATH),
        "baselines": load_json(BASELINES_PATH),
        "clustering": load_json(CLUSTERING_PATH),
        "data": load_json(DATA_SUMMARY_PATH),
    }
