"""RetinaAI assistant – a small, fully offline retrieval chatbot.

How it works (classic NLP, no LLM, no internet):
  1. A hand-written knowledge base of question/answer pairs (below).
  2. Filler words are removed and every question variant is turned into a TF-IDF
     vector (word 1-2 grams + character 3-5 grams, which also tolerates small typos).
  3. A user message is vectorised the same way and compared with cosine
     similarity – i.e. 1-nearest-neighbour search in TF-IDF space.
  4. If the best similarity is below a threshold the bot says it doesn't know
     instead of guessing.
  5. Personal questions ("what is my result?") are answered from the logged-in
     user's own latest screening, respecting the same access rules as the app.
"""
from __future__ import annotations

import re

import numpy as np
from sklearn.feature_extraction.text import ENGLISH_STOP_WORDS, TfidfVectorizer
from sklearn.pipeline import FeatureUnion

from backend import db

KB = [
    # ---------------------------------------------------------- the disease --
    (["what is diabetic retinopathy", "what is dr", "explain diabetic retinopathy", "retinopathy meaning"],
     "Diabetic retinopathy (DR) is damage to the small blood vessels of the retina caused by long-term high blood "
     "sugar. It can leak fluid or blood and, if untreated, lead to vision loss. It is one of the leading causes of "
     "preventable blindness – early screening catches it before eyesight is affected."),
    (["what are the symptoms", "signs of diabetic retinopathy", "symptoms of dr", "how do i know if i have it"],
     "Early DR usually has NO symptoms – that is why yearly eye screening matters. Later signs can include blurred "
     "or fluctuating vision, dark spots or 'floaters', difficulty seeing at night and patches of vision loss. "
     "Sudden vision loss is an emergency – see an eye doctor immediately."),
    (["what are the grades", "dr stages", "what does grade mean", "severity levels", "grade 0 1 2 3 4"],
     "RetinaAI uses the international 5-grade scale: 0 No DR · 1 Mild (only micro-aneurysms) · 2 Moderate · "
     "3 Severe (many haemorrhages, vessel changes) · 4 Proliferative (new abnormal vessels – highest risk). "
     "Grade 2 or higher is called 'referable DR' and needs an ophthalmologist."),
    (["how to prevent diabetic retinopathy", "prevention", "how to reduce risk", "how can i protect my eyes"],
     "Keep blood sugar (HbA1c), blood pressure and cholesterol under control, don't smoke, stay active, take "
     "diabetes medicines as prescribed and get a retinal screening at least once a year."),
    (["is it curable", "treatment for diabetic retinopathy", "how is it treated", "can it be cured"],
     "Damage that has already happened usually cannot be fully reversed, but treatment stops it getting worse: "
     "laser photocoagulation, anti-VEGF injections, steroid injections or surgery (vitrectomy) for advanced cases. "
     "Early stages are managed mainly by controlling sugar and regular check-ups."),
    (["how often should i get screened", "screening frequency", "when to check again", "re screen"],
     "If no referable DR is found: re-screen every 12 months. Mild DR: every 6–12 months as advised. Moderate or "
     "worse: see an ophthalmologist as soon as possible – they will set the follow-up schedule."),
    (["who is at risk", "risk factors", "who gets diabetic retinopathy"],
     "Anyone with type 1 or type 2 diabetes. Risk rises with how many years you have had diabetes, poor sugar "
     "control, high blood pressure, high cholesterol, pregnancy, kidney disease and smoking."),
    (["what is a fundus image", "fundus photo", "retinal photograph", "what picture do i upload"],
     "A fundus image is a photograph of the back of the eye (the retina), taken with a fundus camera or a "
     "smartphone adapter through the pupil. It shows the optic disc, blood vessels and any lesions."),
    (["what are microaneurysms", "haemorrhages", "exudates", "what are lesions", "hard exudates meaning"],
     "Micro-aneurysms are tiny red dots where vessel walls bulge – the earliest sign of DR. Haemorrhages are small "
     "bleeds (red blots). Hard exudates are yellow-white fatty deposits leaking from damaged vessels."),
    # ------------------------------------------------------------- the app --
    (["how do i use the app", "how to screen", "how to upload image", "how to start screening", "steps to use"],
     "Doctors/hospitals: open Screening → choose the patient → upload a fundus photo → click Analyse. You get the "
     "grade, confidence, heat-map, explanation and referral decision, and can download a PDF report. Patients can "
     "see their own results under My Reports."),
    (["what does the heatmap mean", "what is grad cam", "red area in image", "heat map explanation", "explainability"],
     "The heat-map (Grad-CAM++) shows which parts of the retina most influenced the model's decision: red/yellow = "
     "high influence, blue = low. It lets a doctor check the model looked at real lesions and not at glare or dust."),
    (["what does confidence mean", "how sure is the model", "probability meaning", "confidence score"],
     "Confidence is the model's probability for the predicted grade, calibrated with temperature scaling so that "
     "'80 % confident' is right about 80 % of the time. Below ~55 % the app recommends a doctor reviews the image."),
    (["what does refer mean", "referral", "why was i referred", "refer to ophthalmologist meaning"],
     "'Refer' means the probability of moderate-or-worse DR is above a safety threshold, so the patient should see "
     "an eye specialist for a detailed examination. The threshold is set so that at least 90 % of patients who "
     "need a doctor are referred – a missed patient is worse than an extra check-up."),
    (["how accurate is the model", "model accuracy", "how good is it", "performance", "qwk"],
     "On 524 test images it never saw during training: quadratic weighted kappa 0.93, 85.7 % accuracy across the "
     "5 grades, and for referable DR 93 % sensitivity, 95 % specificity and ROC-AUC 0.985. It is still a research "
     "prototype, not a replacement for a doctor."),
    (["which model is used", "what algorithm", "how does it work", "efficientnet", "technology used"],
     "An EfficientNet-B0 convolutional neural network pre-trained on ImageNet and fine-tuned on 3,487 graded "
     "retinal images (APTOS 2019, Aravind Eye Hospital). Images are contrast-enhanced, predictions use test-time "
     "augmentation and calibrated probabilities, and Grad-CAM++ explains each decision."),
    (["image quality warning", "why poor quality", "retake photo", "blurred image", "bad image"],
     "Before grading, the app checks sharpness, brightness, contrast and whether the retina is centred. If the "
     "photo is blurred or badly exposed it warns you – retake the photo for a reliable result."),
    (["image does not look like retina", "out of distribution", "wrong image uploaded", "selfie uploaded"],
     "The app compares the image's features with the training photos (K-nearest-neighbour distance). If it looks "
     "unlike any retinal photo – e.g. a selfie or a document – it warns that the result is unreliable."),
    (["how to download report", "pdf report", "get my report", "print report"],
     "Open the screening (Screening result, Dashboard or My Reports) and click 'Download PDF report'. The PDF "
     "contains the grade, confidence, referral decision, images, heat-map and explanation."),
    # ---------------------------------------------------- accounts & privacy --
    (["who can see my records", "privacy", "is my data safe", "data security", "who can access records"],
     "Access is role-based: a patient sees only their own reports, a doctor only the screenings they performed, a "
     "hospital only screenings done at that hospital, and only the administrator can see all records. Passwords are "
     "stored as salted PBKDF2 hashes and all data stays on this computer."),
    (["what are the roles", "user types", "patient doctor hospital admin", "account types", "login roles"],
     "Patient – view own reports. Doctor – screen patients and see their own screenings. Hospital – screen, add "
     "doctors and see all screenings of the hospital. Admin – manage all users and see every record."),
    (["how to create account", "register", "sign up", "new patient account", "how do i register"],
     "Patients can create an account with 'Register' on the login page. Doctor and hospital accounts are created "
     "by the administrator (hospitals can also add their own doctors) from the Users page."),
    (["forgot password", "reset password", "change password", "cannot login"],
     "Please contact your hospital or the administrator – they can delete and re-create your account. "
     "(Self-service password reset is not part of this prototype.)"),
    (["is this a medical diagnosis", "can i trust it", "disclaimer", "replace doctor"],
     "No. RetinaAI is a screening aid and an educational research prototype. Every referral or treatment decision "
     "must be made by a qualified eye doctor."),
    # ------------------------------------------------------------ small talk --
    (["hi", "hello", "hey", "good morning", "namaste"],
     "Hello! I'm the RetinaAI assistant. Ask me about diabetic retinopathy, how to use the app, what your "
     "result means – or type 'my latest result'."),
    (["thank you", "thanks", "ok thanks", "great"],
     "You're welcome! Remember: keep your sugar under control and get your eyes checked every year."),
    (["who made this", "who built retinaai", "about this project"],
     "RetinaAI was built as a UML501 Machine Learning semester project (SIH 2026 PS-26038 – explainable AI for "
     "diabetic retinopathy screening in rural India)."),
]

SUGGESTIONS = ["What is diabetic retinopathy?", "What do the grades mean?", "What does the heat-map show?",
               "My latest result", "Who can see my records?", "How accurate is the model?"]

PERSONAL = re.compile(r"\b(my|mine)\b.*\b(result|report|grade|screening|status|scan|test)\b|"
                      r"\b(latest|last)\b.*\b(result|report|screening|scan)\b", re.I)

KEEP = {"what", "how", "who", "why", "when", "my", "can", "not"}   # question words carry meaning here
STOP = ENGLISH_STOP_WORDS - KEEP


def clean(text: str) -> str:
    """lower-case, keep letters/digits, drop filler words ("the", "is", "to", ...)."""
    words = re.findall(r"[a-z0-9+]+", text.lower())
    return " ".join(w for w in words if w not in STOP) or text.lower()


_questions = [clean(q) for qs, _ in KB for q in qs]
_answer_of = [i for i, (qs, _) in enumerate(KB) for _ in qs]
_vec = FeatureUnion([
    ("word", TfidfVectorizer(ngram_range=(1, 2), sublinear_tf=True)),
    ("char", TfidfVectorizer(analyzer="char_wb", ngram_range=(3, 5), sublinear_tf=True)),
], transformer_weights={"word": 0.5, "char": 0.5})
_X = _vec.fit_transform(_questions)
THRESHOLD = 0.60


def _personal_answer(user):
    if user is None:
        return "Please log in to ask about your own results."
    rows = db.list_for(user, limit=1)
    if not rows:
        return ("You have no screenings yet." if user["role"] == "patient"
                else "There are no screenings in your records yet.")
    r = rows[0]
    who = "Your latest screening" if user["role"] == "patient" else f"The latest screening ({r['patient_name'] or 'patient'})"
    decision = ("REFER to an ophthalmologist" if r["refer"]
                else "no referral needed – re-screen in 12 months")
    return (f"{who} (#{r['id']}, {r['created_at'][:10]}): {r['grade_name']} with {r['confidence'] * 100:.0f}% "
            f"confidence → {decision}. Follow-up status: {r['followup'].replace('_', ' ')}. "
            f"Open it from {'My Reports' if user['role'] == 'patient' else 'the Dashboard'} to see the heat-map and PDF.")


def answer(message: str, user: dict | None = None) -> dict:
    msg = (message or "").strip()
    if not msg:
        return {"answer": "Type a question, for example 'What is diabetic retinopathy?'", "suggestions": SUGGESTIONS}
    if PERSONAL.search(msg):
        return {"answer": _personal_answer(user), "topic": "personal", "score": 1.0, "suggestions": SUGGESTIONS[:3]}

    q = _vec.transform([clean(msg)])
    # each block is L2-normalised and weighted 0.5, so the dot product is at most 0.5 -> x2 gives a [0, 1] score
    sims = 2 * (_X @ q.T).toarray().ravel()
    best = int(np.argmax(sims))
    score = float(sims[best])
    if score < THRESHOLD:
        return {"answer": "Sorry, I don't know that one yet. I can answer questions about diabetic retinopathy, "
                          "your screening results, the heat-map, accounts and privacy.",
                "topic": None, "score": round(score, 3), "suggestions": SUGGESTIONS}
    idx = _answer_of[best]
    related = [KB[_answer_of[i]][0][0].capitalize() + "?" for i in np.argsort(-sims)
               if _answer_of[i] != idx][:6]
    seen, follow = set(), []
    for q in related:
        if q not in seen:
            seen.add(q)
            follow.append(q)
    return {"answer": KB[idx][1], "topic": KB[idx][0][0], "score": round(score, 3), "suggestions": follow[:3]}
