"use client";

import { useEffect, useRef, useState } from "react";
import { ImagePlus } from "lucide-react";
import { useLang } from "@/lib/i18n";

export default function ImageUploader({ file, onFile }: { file: File | null; onFile: (f: File | null) => void }) {
  const { t } = useLang();
  const input = useRef<HTMLInputElement>(null);
  const [drag, setDrag] = useState(false);
  const [preview, setPreview] = useState<string | null>(null);
  useEffect(() => {
    if (!file) return setPreview(null);
    const url = URL.createObjectURL(file);
    setPreview(url);
    return () => URL.revokeObjectURL(url);
  }, [file]);

  return (
    <div
      onClick={() => input.current?.click()}
      onDragOver={(e) => {
        e.preventDefault();
        setDrag(true);
      }}
      onDragLeave={() => setDrag(false)}
      onDrop={(e) => {
        e.preventDefault();
        setDrag(false);
        const f = e.dataTransfer.files?.[0];
        if (f) onFile(f);
      }}
      className={`flex aspect-square w-full cursor-pointer flex-col items-center justify-center overflow-hidden rounded-2xl border-2 border-dashed text-center transition ${
        drag ? "border-cyan-400 bg-cyan-500/10" : "border-slate-700 bg-slate-950 hover:border-slate-500"
      }`}
    >
      {preview ? (
        // eslint-disable-next-line @next/next/no-img-element
        <img src={preview} alt="selected fundus" className="h-full w-full object-contain" />
      ) : (
        <div className="px-6">
          <ImagePlus className="mx-auto h-10 w-10 text-slate-500" />
          <p className="mt-3 text-sm text-slate-300">{t("drop")}</p>
          <p className="mt-1 text-xs text-slate-500">{t("drop_hint")}</p>
        </div>
      )}
      <input
        ref={input}
        type="file"
        accept="image/*"
        className="hidden"
        onChange={(e) => onFile(e.target.files?.[0] ?? null)}
      />
    </div>
  );
}
