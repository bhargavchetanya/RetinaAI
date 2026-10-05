"use client";

import { useState } from "react";
import { useLang } from "@/lib/i18n";

type View = "heatmap" | "original" | "enhanced";

export default function HeatmapViewer({ images }: { images: { original: string; enhanced: string; heatmap: string } }) {
  const { t } = useLang();
  const [view, setView] = useState<View>("heatmap");
  const [opacity, setOpacity] = useState(1);

  return (
    <div>
      <div className="mb-3 flex gap-1 rounded-lg border border-slate-800 bg-slate-950 p-1 text-sm">
        {(["heatmap", "original", "enhanced"] as View[]).map((v) => (
          <button
            key={v}
            onClick={() => setView(v)}
            className={`flex-1 rounded-md px-3 py-1.5 ${view === v ? "bg-slate-800 text-white" : "text-slate-400 hover:text-white"}`}
          >
            {t(v)}
          </button>
        ))}
      </div>
      <div className="relative aspect-square w-full overflow-hidden rounded-xl bg-black">
        {/* eslint-disable @next/next/no-img-element */}
        <img src={view === "enhanced" ? images.enhanced : images.original} alt="fundus" className="absolute inset-0 h-full w-full object-contain" />
        {view === "heatmap" && (
          <img src={images.heatmap} alt="Grad-CAM++ heat-map" style={{ opacity }} className="absolute inset-0 h-full w-full object-contain" />
        )}
      </div>
      {view === "heatmap" && (
        <div className="mt-3">
          <label className="flex items-center gap-3 text-xs text-slate-400">
            <span className="whitespace-nowrap">{t("original")}</span>
            <input
              type="range"
              min={0}
              max={1}
              step={0.05}
              value={opacity}
              onChange={(e) => setOpacity(parseFloat(e.target.value))}
              className="w-full accent-cyan-500"
              aria-label="heat-map opacity"
            />
            <span className="whitespace-nowrap">{t("heatmap")}</span>
          </label>
          <p className="mt-2 text-xs text-slate-500">{t("heat_help")}</p>
        </div>
      )}
    </div>
  );
}
