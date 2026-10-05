"use client";

import { createContext, useContext, useState } from "react";

export type Lang = "en" | "hi";

const STRINGS = {
  en: {
    nav_home: "Home",
    nav_screen: "Screening",
    nav_dashboard: "Dashboard",
    nav_model: "Model",
    screen_title: "Retinal screening",
    screen_sub: "Upload a fundus photograph. The model grades diabetic retinopathy and shows where it looked.",
    patient: "Patient details (optional)",
    name: "Name",
    age: "Age",
    sex: "Sex",
    male: "Male",
    female: "Female",
    other: "Other",
    eye: "Eye",
    left: "Left",
    right: "Right",
    dm_years: "Years with diabetes",
    centre: "Health centre",
    drop: "Drop a fundus image here, or click to choose",
    drop_hint: "PNG / JPG from a fundus camera or smartphone adapter",
    analyse: "Analyse image",
    analysing: "Analysing…",
    new_scan: "New screening",
    result: "Result",
    grade: "DR grade",
    confidence: "Confidence",
    p_ref: "Probability of referable DR",
    refer: "Refer to ophthalmologist",
    no_refer: "No referral needed",
    explanation: "Why the model decided this",
    original: "Original",
    enhanced: "Enhanced",
    heatmap: "Heat-map",
    probabilities: "Grade probabilities",
    quality: "Image quality",
    quality_ok: "Adequate",
    quality_bad: "Poor – retake advised",
    ood_warn: "This image does not look like the retinal photos the model was trained on. The result may be unreliable.",
    report: "Download PDF report",
    heat_help: "Red/yellow = regions that most influenced the prediction (Grad-CAM++).",
    model_missing: "Model not loaded",
    backend_down: "Cannot reach the backend at",
  },
  hi: {
    nav_home: "होम",
    nav_screen: "जाँच",
    nav_dashboard: "डैशबोर्ड",
    nav_model: "मॉडल",
    screen_title: "रेटिना जाँच",
    screen_sub: "आँख के पर्दे (फंडस) की फ़ोटो अपलोड करें। मॉडल DR का स्तर बताएगा और दिखाएगा कि उसने कहाँ देखा।",
    patient: "मरीज़ की जानकारी (वैकल्पिक)",
    name: "नाम",
    age: "उम्र",
    sex: "लिंग",
    male: "पुरुष",
    female: "महिला",
    other: "अन्य",
    eye: "आँख",
    left: "बाईं",
    right: "दाईं",
    dm_years: "डायबिटीज़ के वर्ष",
    centre: "स्वास्थ्य केंद्र",
    drop: "फंडस फ़ोटो यहाँ छोड़ें या चुनने के लिए क्लिक करें",
    drop_hint: "फंडस कैमरा या स्मार्टफ़ोन अडैप्टर से PNG / JPG",
    analyse: "जाँच करें",
    analysing: "जाँच हो रही है…",
    new_scan: "नई जाँच",
    result: "परिणाम",
    grade: "DR स्तर",
    confidence: "भरोसा",
    p_ref: "रेफ़रल योग्य DR की संभावना",
    refer: "नेत्र विशेषज्ञ के पास भेजें",
    no_refer: "रेफ़रल की आवश्यकता नहीं",
    explanation: "मॉडल ने यह निर्णय क्यों लिया",
    original: "मूल",
    enhanced: "उन्नत",
    heatmap: "हीट-मैप",
    probabilities: "स्तर की संभावनाएँ",
    quality: "छवि गुणवत्ता",
    quality_ok: "ठीक",
    quality_bad: "खराब – फिर से फ़ोटो लें",
    ood_warn: "यह छवि प्रशिक्षण वाली रेटिना फ़ोटो जैसी नहीं दिखती। परिणाम अविश्वसनीय हो सकता है।",
    report: "PDF रिपोर्ट डाउनलोड करें",
    heat_help: "लाल/पीला = वे क्षेत्र जिन्होंने निर्णय को सबसे अधिक प्रभावित किया (Grad-CAM++)।",
    model_missing: "मॉडल लोड नहीं हुआ",
    backend_down: "बैकएंड से संपर्क नहीं हो पा रहा:",
  },
} as const;

export type StringKey = keyof (typeof STRINGS)["en"];

const Ctx = createContext<{ lang: Lang; setLang: (l: Lang) => void; t: (k: StringKey) => string }>({
  lang: "en",
  setLang: () => {},
  t: (k) => STRINGS.en[k],
});

export function LangProvider({ children }: { children: React.ReactNode }) {
  const [lang, setLangState] = useState<Lang>("en");
  const setLang = (l: Lang) => {
    setLangState(l);
    try {
      localStorage.setItem("retina-lang", l);
    } catch {}
  };
  return <Ctx.Provider value={{ lang, setLang, t: (k) => STRINGS[lang][k] }}>{children}</Ctx.Provider>;
}

export const useLang = () => useContext(Ctx);
