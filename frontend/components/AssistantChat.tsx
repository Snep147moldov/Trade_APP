"use client";

import { useRef, useState } from "react";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { api, pretty, type ChatMessage } from "@/lib/api";

const SUGGESTIONS = [
  "Почему инструмент двигался сегодня?",
  "Что сейчас показывает RSI и MACD?",
  "Какие риски у сделки по текущему сигналу?",
  "Какие важные события в календаре сегодня?",
  "Что говорит моя статистика — где я ошибаюсь?",
];

export function AssistantChat({ instrument, timeframe, aiEnabled }: {
  instrument: string | null;
  timeframe: string;
  aiEnabled: boolean;
}) {
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [input, setInput] = useState("");
  const [busy, setBusy] = useState(false);
  const scrollRef = useRef<HTMLDivElement>(null);

  const ask = async (text: string) => {
    const q = text.trim();
    if (!q || busy) return;
    setInput("");
    setBusy(true);
    const history = messages;
    setMessages((m) => [...m, { role: "user", content: q }]);
    setTimeout(() => scrollRef.current?.scrollTo({ top: 1e6 }), 50);
    try {
      const r = await api.chat(q, history, instrument ?? "", timeframe);
      setMessages((m) => [...m, { role: "assistant", content: r.reply }]);
    } catch (e) {
      setMessages((m) => [...m, {
        role: "assistant",
        content: e instanceof Error && e.message.includes("400")
          ? "Не задан Anthropic API ключ — добавьте его в «Подключениях»."
          : "Не удалось получить ответ — попробуйте ещё раз.",
      }]);
    }
    setBusy(false);
    setTimeout(() => scrollRef.current?.scrollTo({ top: 1e6, behavior: "smooth" }), 50);
  };

  return (
    <Card className="rounded-2xl border-black/5 shadow-sm">
      <CardContent className="pt-4">
        <div className="mb-2 flex items-center justify-between">
          <h3 className="text-sm font-semibold tracking-tight">ИИ-ассистент</h3>
          <span className="text-[10px] text-muted-foreground">
            {instrument ? `контекст: ${pretty(instrument)} · ${timeframe}` : "общий контекст"}
          </span>
        </div>

        <div ref={scrollRef} className="mb-3 h-[320px] space-y-2 overflow-y-auto rounded-xl bg-black/[0.02] p-3">
          {messages.length === 0 && (
            <div className="space-y-1.5">
              <p className="text-xs text-muted-foreground">
                Задайте вопрос — ассистент видит технику, паттерны, новости,
                календарь, портфель и накопленную память.
              </p>
              {SUGGESTIONS.map((s) => (
                <button key={s} onClick={() => ask(s)}
                        className="block w-full rounded-lg bg-white px-3 py-1.5 text-left text-xs text-[#0a84ff] shadow-sm hover:bg-[#0a84ff]/5">
                  {s}
                </button>
              ))}
            </div>
          )}
          {messages.map((m, i) => (
            <div key={i} className={`flex ${m.role === "user" ? "justify-end" : "justify-start"}`}>
              <div className={`max-w-[85%] whitespace-pre-wrap rounded-2xl px-3 py-2 text-xs leading-relaxed ${
                m.role === "user" ? "bg-[#0a84ff] text-white" : "bg-white shadow-sm"
              }`}>
                {m.content}
              </div>
            </div>
          ))}
          {busy && <p className="text-xs text-muted-foreground">Ассистент думает…</p>}
        </div>

        <form className="flex gap-2" onSubmit={(e) => { e.preventDefault(); ask(input); }}>
          <Input className="rounded-xl" placeholder={aiEnabled ? "Спросите о рынке, рисках, индикаторах…" : "Нужен Anthropic API ключ (Подключения)"}
                 value={input} onChange={(e) => setInput(e.target.value)} disabled={busy} />
          <Button type="submit" className="rounded-xl" disabled={busy || !input.trim()}>
            Спросить
          </Button>
        </form>
      </CardContent>
    </Card>
  );
}
