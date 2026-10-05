"use client";

import type { Probability } from "@/types";
import { useLang } from "@/lib/i18n";

/** Horizontal bar per DR grade. Single series: the predicted grade is drawn in
 *  the series colour, the rest in a muted tone; every bar is labelled. */
export default function ConfidenceChart({ probs, predicted }: { probs: Probability[]; predicted: number }) {
  const { lang } = useLang();
  return (
    <div className="space-y-2.5" role="table" aria-label="grade probabilities">
      {probs.map((p) => {
        const pct = p.p * 100;
        const active = p.grade === predicted;
        return (
          <div key={p.grade} role="row" className="group" title={`${p.name}: ${pct.toFixed(1)}%`}>
            <div className="mb-1 flex justify-between text-xs">
              <span role="cell" className={active ? "font-semibold text-slate-100" : "text-slate-400"}>
                {p.grade} · {lang === "hi" ? p.name_hi : p.name}
              </span>
              <span role="cell" className="tabular text-slate-300">
                {pct.toFixed(1)}%
              </span>
            </div>
            <div className="h-2.5 w-full rounded bg-slate-800">
              <div
                className="h-2.5 rounded transition-all group-hover:brightness-125"
                style={{ width: `${Math.max(pct, 0.5)}%`, background: active ? "var(--series-1)" : "#475569" }}
              />
            </div>
          </div>
        );
      })}
    </div>
  );
}
