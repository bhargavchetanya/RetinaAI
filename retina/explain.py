"""Turns a Grad-CAM heat-map into a short, non-technical explanation.

1. Locate the hot region(s): threshold the CAM at its 85th percentile, find
   connected components, and describe where the biggest one is (upper-left,
   centre, ...) and whether attention is focal or scattered.
2. Look *inside* the hot region of the original photo for colour/shape cues:
     - bright yellow-white spots  -> pattern consistent with hard exudates
     - small dark-red spots       -> micro-aneurysms / haemorrhages
   (green-channel top-hat / black-hat morphology, a classical image-processing
   lesion detector).
3. Combine with the predicted grade and the referral decision.

The lesion words are hints for the health worker ("consistent with"), not a
diagnosis – the heat-map is what they should look at.
"""
from __future__ import annotations

import cv2
import numpy as np

from .config import CLASS_NAMES, REFERABLE_GRADE

_POS_EN = {
    ("upper", "left"): "upper-left", ("upper", "right"): "upper-right",
    ("lower", "left"): "lower-left", ("lower", "right"): "lower-right",
}
_POS_HI = {
    "upper-left": "ऊपरी-बाएँ", "upper-right": "ऊपरी-दाएँ", "lower-left": "निचले-बाएँ",
    "lower-right": "निचले-दाएँ", "central": "मध्य",
}

GRADE_TEXT = {
    0: ("No signs of diabetic retinopathy were detected.",
        "डायबिटिक रेटिनोपैथी के कोई लक्षण नहीं मिले।"),
    1: ("Early (mild) changes – usually only micro-aneurysms.",
        "शुरुआती (हल्के) बदलाव – आमतौर पर केवल माइक्रो-एन्यूरिज़्म।"),
    2: ("Moderate non-proliferative changes – more lesions than micro-aneurysms alone.",
        "मध्यम नॉन-प्रोलिफ़रेटिव बदलाव – माइक्रो-एन्यूरिज़्म से अधिक घाव।"),
    3: ("Severe non-proliferative changes – widespread haemorrhages / vessel changes.",
        "गंभीर नॉन-प्रोलिफ़रेटिव बदलाव – व्यापक रक्तस्राव / नसों में बदलाव।"),
    4: ("Proliferative changes – risk of new abnormal vessel growth.",
        "प्रोलिफ़रेटिव बदलाव – नई असामान्य नसें बनने का खतरा।"),
}


def _lesion_cues(rgb: np.ndarray, region: np.ndarray, retina: np.ndarray) -> dict:
    g = rgb[..., 1]
    k = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (15, 15))
    tophat = cv2.morphologyEx(g, cv2.MORPH_TOPHAT, k)      # small bright blobs
    blackhat = cv2.morphologyEx(g, cv2.MORPH_BLACKHAT, k)  # small dark blobs
    r, b = rgb[..., 0].astype(int), rgb[..., 2].astype(int)
    yellow = (tophat > 25) & (r > b + 40)                 # bright & yellowish
    red_dark = (blackhat > 18) & (r > g.astype(int) + 20)  # dark, reddish
    area = max(region.sum(), 1)
    ret_area = max(retina.sum(), 1)
    # How much denser the cue is inside the hot region than across the retina
    def ratio(m):
        inside = (m & region).sum() / area
        overall = (m & retina).sum() / ret_area
        return float(inside), float(inside / overall) if overall > 0 else 0.0
    return {"bright": ratio(yellow), "dark": ratio(red_dark)}


def explain(cam: np.ndarray, display_rgb: np.ndarray, grade: int, confidence: float,
            refer: bool, quality_ok: bool = True) -> dict:
    h, w = display_rgb.shape[:2]
    cam = cv2.resize(cam, (w, h))
    retina = display_rgb.max(axis=2) > 10
    cam = cam * retina
    thr = np.percentile(cam[retina], 85) if retina.any() else 0.5
    hot = (cam >= thr) & retina

    n, lab, stats, cents = cv2.connectedComponentsWithStats(hot.astype(np.uint8))
    comps = [(stats[i, cv2.CC_STAT_AREA], cents[i]) for i in range(1, n)
             if stats[i, cv2.CC_STAT_AREA] > 0.004 * h * w]
    comps.sort(key=lambda t: -t[0])

    if comps:
        cx, cy = comps[0][1]
        dx, dy = cx / w - 0.5, cy / h - 0.5
        if (dx ** 2 + dy ** 2) ** 0.5 < 0.12:
            where = "central"
        else:
            where = _POS_EN[("upper" if dy < 0 else "lower", "left" if dx < 0 else "right")]
    else:
        where = "central"
    spread = "scattered" if len(comps) >= 3 else "focal"

    cues = _lesion_cues(display_rgb, hot, retina)
    lesions_en, lesions_hi = [], []
    if cues["dark"][1] > 1.3 and cues["dark"][0] > 0.002:
        lesions_en.append("small dark-red spots (consistent with micro-aneurysms / haemorrhages)")
        lesions_hi.append("छोटे गहरे-लाल धब्बे (माइक्रो-एन्यूरिज़्म / रक्तस्राव जैसे)")
    if cues["bright"][1] > 1.3 and cues["bright"][0] > 0.002:
        lesions_en.append("bright yellowish deposits (consistent with hard exudates)")
        lesions_hi.append("चमकीले पीले जमाव (हार्ड एक्सयूडेट जैसे)")

    region_en = f"the {where} region of the retina" if where != "central" else "the central region of the retina"
    region_hi = f"रेटिना के {_POS_HI[where]} भाग"

    if grade == 0:
        focus_en = (f"The model's attention was spread over normal structures, mostly {region_en}; "
                    "no lesion pattern dominated its decision.")
        focus_hi = f"मॉडल का ध्यान सामान्य संरचनाओं पर था, मुख्यतः {region_hi} पर; कोई घाव प्रमुख नहीं था।"
    else:
        focus_en = (f"The model focused on {'several scattered areas, mainly ' if spread == 'scattered' else ''}"
                    f"{region_en}")
        focus_hi = f"मॉडल ने {'कई बिखरे हुए क्षेत्रों पर, मुख्यतः ' if spread == 'scattered' else ''}{region_hi} पर ध्यान दिया"
        if lesions_en:
            focus_en += ", where it found " + " and ".join(lesions_en) + "."
            focus_hi += ", जहाँ " + " और ".join(lesions_hi) + " दिखे।"
        else:
            focus_en += "."
            focus_hi += "।"

    if not quality_ok:
        action_en = "Image quality is poor – please retake the photo before relying on this result."
        action_hi = "छवि की गुणवत्ता खराब है – कृपया परिणाम पर भरोसा करने से पहले फिर से फ़ोटो लें।"
    elif refer and grade < REFERABLE_GRADE:
        action_en = ("However, the combined probability of moderate-or-worse DR is above the safety threshold, "
                     "so as a precaution: REFER to an ophthalmologist.")
        action_hi = ("फिर भी मध्यम या गंभीर DR की कुल संभावना सुरक्षा सीमा से अधिक है, इसलिए सावधानी के तौर पर "
                     "नेत्र रोग विशेषज्ञ के पास भेजें।")
    elif refer:
        action_en = "REFER to an ophthalmologist for a detailed eye examination."
        action_hi = "विस्तृत आँखों की जाँच के लिए नेत्र रोग विशेषज्ञ के पास भेजें।"
    else:
        action_en = "No referral needed now. Re-screen in 12 months and keep blood sugar under control."
        action_hi = "अभी रेफ़रल की आवश्यकता नहीं। 12 महीने में फिर से जाँच करें और शुगर नियंत्रित रखें।"

    if confidence < 0.55:
        action_en += " (Low model confidence – a doctor should review this image.)"
        action_hi += " (मॉडल का भरोसा कम है – डॉक्टर को यह छवि देखनी चाहिए।)"

    return {
        "en": f"{GRADE_TEXT[grade][0]} {focus_en} {action_en}",
        "hi": f"{GRADE_TEXT[grade][1]} {focus_hi} {action_hi}",
        "focus_region": where,
        "attention_pattern": spread,
        "lesion_cues": lesions_en,
        "grade_name": CLASS_NAMES[grade],
        "referable": bool(refer),
    }
