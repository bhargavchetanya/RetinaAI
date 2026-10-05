"use client";

/** Shared Recharts styling: recessive grid/axes, thin marks, dark tooltip. */
export const axisProps = {
  stroke: "var(--axis)",
  tick: { fill: "var(--text-muted)", fontSize: 11 },
  tickLine: false,
} as const;

export const gridProps = { stroke: "var(--grid)", strokeDasharray: "0", vertical: false } as const;

export const tooltipProps = {
  contentStyle: {
    background: "#0b1220",
    border: "1px solid rgba(255,255,255,0.12)",
    borderRadius: 8,
    fontSize: 12,
    color: "var(--text-primary)",
  },
  labelStyle: { color: "var(--text-secondary)" },
  itemStyle: { color: "var(--text-primary)" },
  cursor: { fill: "rgba(148,163,184,0.08)", stroke: "var(--axis)" },
} as const;

export function Legend({ items }: { items: { label: string; color: string; dashed?: boolean }[] }) {
  return (
    <div className="flex flex-wrap gap-4 text-xs text-slate-300">
      {items.map((i) => (
        <span key={i.label} className="flex items-center gap-1.5">
          <span
            className="inline-block h-0.5 w-4"
            style={{ background: i.dashed ? "none" : i.color, borderTop: i.dashed ? `2px dashed ${i.color}` : undefined }}
          />
          {i.label}
        </span>
      ))}
    </div>
  );
}

export function StatTile({ label, value, sub }: { label: string; value: string | number; sub?: string }) {
  return (
    <div className="card">
      <div className="label">{label}</div>
      <div className="mt-2 text-3xl font-bold text-slate-50">{value}</div>
      {sub && <div className="mt-1 text-xs text-slate-500">{sub}</div>}
    </div>
  );
}
