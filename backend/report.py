"""Auto-generated screening report (PDF) – attach to a referral letter."""
from __future__ import annotations

import base64
import io
from pathlib import Path

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import Image, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

from .db import STORAGE

IMG_DIR = STORAGE / "images"
IMG_DIR.mkdir(exist_ok=True)


def save_images(sid: int, images: dict):
    for k in ("original", "heatmap"):
        data = images[k].split(",", 1)[1]
        (IMG_DIR / f"{sid}_{k}.png").write_bytes(base64.b64decode(data))


def build_pdf(s: dict) -> bytes:
    r = s["result"]
    buf = io.BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=A4, leftMargin=16 * mm, rightMargin=16 * mm,
                            topMargin=14 * mm, bottomMargin=14 * mm,
                            title=f"RetinaAI screening #{s['id']}")
    ss = getSampleStyleSheet()
    h = ParagraphStyle("h", parent=ss["Title"], fontSize=17, spaceAfter=2, textColor=colors.HexColor("#0e7490"))
    sub = ParagraphStyle("s", parent=ss["Normal"], fontSize=8.5, textColor=colors.grey)
    body = ParagraphStyle("b", parent=ss["Normal"], fontSize=10, leading=14)
    sec = ParagraphStyle("sec", parent=ss["Heading3"], fontSize=11.5, spaceBefore=8, spaceAfter=4)
    refer = r["refer"]
    el = [Paragraph("RetinaAI – Diabetic Retinopathy Screening Report", h),
          Paragraph(f"Report #{s['id']} &nbsp;·&nbsp; {s['created_at'].replace('T', ' ')} &nbsp;·&nbsp; "
                    f"model {r.get('model_version', '')}", sub), Spacer(1, 6)]

    info = [["Patient", s.get("patient_name") or "—", "Age / Sex",
             f"{s.get('patient_age') or '—'} / {s.get('patient_sex') or '—'}"],
            ["Eye", {"L": "Left", "R": "Right"}.get(s.get("eye") or "", "—"), "Diabetes (years)",
             str(s.get("diabetes_years") or "—")],
            ["Health centre", s.get("centre") or "—", "Image quality",
             "Adequate" if r["quality"]["ok"] else "POOR – " + ", ".join(r["quality"]["issues"])]]
    t = Table(info, colWidths=[30 * mm, 60 * mm, 32 * mm, 56 * mm])
    t.setStyle(TableStyle([("FONTSIZE", (0, 0), (-1, -1), 9), ("TEXTCOLOR", (0, 0), (0, -1), colors.grey),
                           ("TEXTCOLOR", (2, 0), (2, -1), colors.grey),
                           ("LINEBELOW", (0, 0), (-1, -1), 0.25, colors.lightgrey)]))
    el += [t, Spacer(1, 8)]

    color = colors.HexColor("#b91c1c") if refer else colors.HexColor("#15803d")
    verdict = "REFER TO OPHTHALMOLOGIST" if refer else "NO REFERRAL NEEDED – re-screen in 12 months"
    box = Table([[Paragraph(f"<b>{r['grade_name']}</b> (grade {r['grade']}/4) &nbsp; · &nbsp; "
                            f"confidence {r['confidence'] * 100:.0f}% &nbsp; · &nbsp; "
                            f"P(referable DR) {r['p_referable'] * 100:.0f}%", body)],
                 [Paragraph(f"<font color='white'><b>{verdict}</b></font>", body)]], colWidths=[178 * mm])
    box.setStyle(TableStyle([("BACKGROUND", (0, 1), (0, 1), color), ("BOX", (0, 0), (-1, -1), 0.8, color),
                             ("TOPPADDING", (0, 0), (-1, -1), 6), ("BOTTOMPADDING", (0, 0), (-1, -1), 6)]))
    el += [box, Spacer(1, 8)]

    o, hm = IMG_DIR / f"{s['id']}_original.png", IMG_DIR / f"{s['id']}_heatmap.png"
    if o.exists() and hm.exists():
        imgs = Table([[Image(str(o), 80 * mm, 80 * mm), Image(str(hm), 80 * mm, 80 * mm)],
                      [Paragraph("Fundus image (cropped)", sub), Paragraph("Grad-CAM++ attention map", sub)]],
                     colWidths=[89 * mm, 89 * mm])
        imgs.setStyle(TableStyle([("ALIGN", (0, 0), (-1, -1), "CENTER")]))
        el += [imgs]

    el += [Paragraph("Explanation", sec), Paragraph(r["explanation"]["en"], body)]
    if r.get("warnings"):
        w = {"quality": "Image quality is below the recommended level – retake advised.",
             "out_of_distribution": "Image looks unlike the retinal photos the model was trained on – "
                                    "result may be unreliable."}
        el += [Paragraph("<font color='#b45309'><b>Warnings:</b> " +
                         " ".join(w.get(x, x) for x in r["warnings"]) + "</font>", body)]

    el += [Paragraph("Grade probabilities", sec)]
    pt = Table([["Grade", "Probability"]] + [[p["name"], f"{p['p'] * 100:.1f}%"] for p in r["probabilities"]],
               colWidths=[60 * mm, 30 * mm])
    pt.setStyle(TableStyle([("FONTSIZE", (0, 0), (-1, -1), 9), ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#e2e8f0")),
                            ("GRID", (0, 0), (-1, -1), 0.25, colors.lightgrey),
                            ("BACKGROUND", (0, r["grade"] + 1), (-1, r["grade"] + 1), colors.HexColor("#cffafe"))]))
    el += [pt, Spacer(1, 10),
           Paragraph("This is an AI-assisted screening result produced by a research prototype "
                     "(EfficientNet-B0 trained on APTOS-2019). It is not a medical diagnosis; "
                     "the final decision rests with a qualified ophthalmologist.", sub)]
    doc.build(el)
    return buf.getvalue()
