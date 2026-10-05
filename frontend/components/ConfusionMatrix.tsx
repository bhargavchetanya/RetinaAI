"use client";

const NAMES = ["No DR", "Mild", "Moderate", "Severe", "Prolif."];
// sequential blue ramp (light → dark = low → high), from the reference palette
const RAMP = ["#1e293b", "#104281", "#184f95", "#1c5cab", "#256abf", "#2a78d6", "#3987e5", "#5598e7"];

/** Row-normalised confusion matrix: colour = share of the true class, number = count. */
export default function ConfusionMatrix({ cm }: { cm: number[][] }) {
  return (
    <div className="overflow-x-auto">
      <table className="tabular mx-auto border-separate text-xs" style={{ borderSpacing: 2 }}>
        <thead>
          <tr>
            <th />
            <th colSpan={5} className="pb-1 text-center font-normal text-slate-400">
              Predicted
            </th>
          </tr>
          <tr>
            <th className="pr-2 text-right font-normal text-slate-400">True ↓</th>
            {NAMES.map((n) => (
              <th key={n} className="w-14 px-1 pb-1 text-center font-normal text-slate-400">
                {n}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {cm.map((row, i) => {
            const total = row.reduce((a, b) => a + b, 0) || 1;
            return (
              <tr key={i}>
                <td className="pr-2 text-right text-slate-400">{NAMES[i]}</td>
                {row.map((v, j) => {
                  const share = v / total;
                  const bg = RAMP[Math.min(RAMP.length - 1, Math.round(share * (RAMP.length - 1)))];
                  return (
                    <td
                      key={j}
                      title={`true ${NAMES[i]} → predicted ${NAMES[j]}: ${v} (${(share * 100).toFixed(0)}% of row)`}
                      className={`h-12 w-14 rounded text-center ${i === j ? "font-semibold" : ""}`}
                      style={{ background: bg, color: "#f8fafc", outline: i === j ? "1px solid rgba(255,255,255,0.35)" : undefined }}
                    >
                      {v}
                    </td>
                  );
                })}
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}
