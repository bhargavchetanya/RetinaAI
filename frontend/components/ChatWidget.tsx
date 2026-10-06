"use client";

import { useEffect, useRef, useState } from "react";
import { Bot, MessageCircle, Send, X } from "lucide-react";
import { api } from "@/lib/api";

interface Msg {
  from: "bot" | "user";
  text: string;
}

const START: Msg = {
  from: "bot",
  text: "Hi! I'm the RetinaAI assistant. Ask me about diabetic retinopathy, your results, the heat-map or your account.",
};
const FIRST_SUGGESTIONS = ["What is diabetic retinopathy?", "What do the grades mean?", "My latest result", "Who can see my records?"];

/** Floating help chat – answers come from the offline retrieval bot in backend/chatbot.py. */
export default function ChatWidget() {
  const [open, setOpen] = useState(false);
  const [msgs, setMsgs] = useState<Msg[]>([START]);
  const [suggestions, setSuggestions] = useState<string[]>(FIRST_SUGGESTIONS);
  const [text, setText] = useState("");
  const [busy, setBusy] = useState(false);
  const end = useRef<HTMLDivElement>(null);

  useEffect(() => {
    end.current?.scrollIntoView({ behavior: "smooth" });
  }, [msgs, open]);

  async function send(q: string) {
    const message = q.trim();
    if (!message || busy) return;
    setMsgs((m) => [...m, { from: "user", text: message }]);
    setText("");
    setBusy(true);
    try {
      const r = await api.chat(message);
      setMsgs((m) => [...m, { from: "bot", text: r.answer }]);
      setSuggestions(r.suggestions ?? []);
    } catch {
      setMsgs((m) => [...m, { from: "bot", text: "I can't reach the server right now. Is the backend running?" }]);
    } finally {
      setBusy(false);
    }
  }

  return (
    <>
      {open && (
        <div className="fixed bottom-24 right-4 z-40 flex h-[32rem] max-h-[75vh] w-[22rem] max-w-[calc(100vw-2rem)] flex-col overflow-hidden rounded-2xl border border-slate-700 bg-slate-950 shadow-2xl">
          <div className="flex items-center gap-2 border-b border-slate-800 bg-slate-900 px-4 py-3">
            <Bot className="h-5 w-5 text-cyan-400" />
            <div className="flex-1">
              <div className="text-sm font-semibold">RetinaAI assistant</div>
              <div className="text-xs text-slate-500">Offline FAQ bot · not medical advice</div>
            </div>
            <button onClick={() => setOpen(false)} className="text-slate-400 hover:text-white" aria-label="Close chat">
              <X className="h-5 w-5" />
            </button>
          </div>
          <div className="flex-1 space-y-3 overflow-y-auto p-4">
            {msgs.map((m, i) => (
              <div key={i} className={`flex ${m.from === "user" ? "justify-end" : "justify-start"}`}>
                <div
                  className={`max-w-[85%] whitespace-pre-line rounded-2xl px-3 py-2 text-sm leading-6 ${
                    m.from === "user" ? "bg-cyan-500 text-slate-950" : "bg-slate-800 text-slate-100"
                  }`}
                >
                  {m.text}
                </div>
              </div>
            ))}
            {busy && <div className="text-xs text-slate-500">typing…</div>}
            <div ref={end} />
          </div>
          {suggestions.length > 0 && (
            <div className="flex flex-wrap gap-1.5 border-t border-slate-800 px-3 pt-2">
              {suggestions.map((s) => (
                <button
                  key={s}
                  onClick={() => send(s)}
                  className="rounded-full border border-slate-700 px-2.5 py-1 text-xs text-slate-300 hover:border-cyan-500 hover:text-white"
                >
                  {s}
                </button>
              ))}
            </div>
          )}
          <form
            onSubmit={(e) => {
              e.preventDefault();
              send(text);
            }}
            className="flex gap-2 p-3"
          >
            <input
              className="input"
              placeholder="Type a question…"
              value={text}
              onChange={(e) => setText(e.target.value)}
              maxLength={500}
            />
            <button
              disabled={busy || !text.trim()}
              className="rounded-lg bg-cyan-500 px-3 text-slate-950 hover:bg-cyan-400 disabled:opacity-40"
              aria-label="Send"
            >
              <Send className="h-4 w-4" />
            </button>
          </form>
        </div>
      )}
      <button
        onClick={() => setOpen((o) => !o)}
        className="fixed bottom-5 right-4 z-40 flex h-14 w-14 items-center justify-center rounded-full bg-cyan-500 text-slate-950 shadow-lg hover:bg-cyan-400"
        aria-label={open ? "Close assistant" : "Open assistant"}
      >
        {open ? <X className="h-6 w-6" /> : <MessageCircle className="h-6 w-6" />}
      </button>
    </>
  );
}
