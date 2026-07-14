"use client";

import { useCallback, useEffect, useState } from "react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { api, type MemoryItem } from "@/lib/api";

const KIND_LABEL: Record<string, string> = {
  lesson: "урок",
  trade_review: "разбор сделки",
  pattern_stat: "статистика",
  regime: "режим/фон",
  user_style: "стиль",
  journal_insight: "инсайт журнала",
};

export function MemoryPanel({ aiEnabled }: { aiEnabled: boolean }) {
  const [items, setItems] = useState<MemoryItem[]>([]);
  const [title, setTitle] = useState("");
  const [content, setContent] = useState("");
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState<string | null>(null);

  const refresh = useCallback(async () => {
    try {
      setItems((await api.memory()).memories);
    } catch {
      /* ignore */
    }
  }, []);

  useEffect(() => {
    refresh();
  }, [refresh]);

  const addNote = async () => {
    if (!title.trim() || !content.trim()) return;
    await api.addMemory(title, content).catch(() => {});
    setTitle("");
    setContent("");
    refresh();
  };

  const consolidate = async () => {
    setBusy(true);
    setMessage(null);
    try {
      const r = await api.consolidateMemory();
      setMessage(r.created.length
        ? `Создано уроков: ${r.created.length}`
        : "Пока недостаточно новых закрытых сделок для новых уроков.");
      refresh();
    } catch (e) {
      setMessage(e instanceof Error && e.message.includes("400")
        ? "Нужен Anthropic API ключ." : "Ошибка консолидации.");
    }
    setBusy(false);
  };

  return (
    <Card className="rounded-2xl border-black/5 shadow-sm">
      <CardContent className="pt-4">
        <div className="mb-2 flex items-center justify-between">
          <h3 className="text-sm font-semibold tracking-tight">
            ИИ-память · {items.length} записей
          </h3>
          <Button size="sm" variant="outline" className="rounded-xl"
                  onClick={consolidate} disabled={busy || !aiEnabled}>
            {busy ? "Консолидирую…" : "Извлечь уроки сейчас"}
          </Button>
        </div>
        <p className="mb-3 text-[11px] text-muted-foreground">
          Система запоминает каждый закрытый сигнал, считает hit-rate факторов,
          хранит уроки и ваш стиль. Всё это подмешивается в промпты ИИ — оценки
          становятся точнее с опытом. {message && <span className="text-[#0a84ff]">{message}</span>}
        </p>

        <div className="mb-3 flex gap-2">
          <Input className="w-[200px] rounded-xl" placeholder="Заголовок заметки"
                 value={title} onChange={(e) => setTitle(e.target.value)} />
          <Input className="flex-1 rounded-xl" placeholder="Что ИИ должен помнить (например: не торгую по пятницам)"
                 value={content} onChange={(e) => setContent(e.target.value)} />
          <Button className="rounded-xl" variant="outline" onClick={addNote}
                  disabled={!title.trim() || !content.trim()}>
            Запомнить
          </Button>
        </div>

        <div className="max-h-[420px] space-y-1.5 overflow-y-auto">
          {items.length === 0 && (
            <p className="py-4 text-center text-xs text-muted-foreground">
              Память пуста — появится после первых закрытых сделок.
            </p>
          )}
          {items.map((m) => (
            <div key={m.id} className="rounded-xl bg-black/[0.02] px-3 py-2">
              <div className="flex items-center gap-2">
                <Badge variant="secondary" className="rounded-full text-[9px]">
                  {KIND_LABEL[m.kind] ?? m.kind}
                </Badge>
                {m.instrument && (
                  <span className="text-[10px] text-muted-foreground">{m.instrument}</span>
                )}
                <p className="truncate text-xs font-medium">{m.title}</p>
                <span className="ml-auto text-[9px] tabular-nums text-muted-foreground">
                  важность {(m.importance * 100).toFixed(0)}%
                </span>
                <button className="text-[10px] text-[#ff3b30]"
                        onClick={async () => { await api.deleteMemory(m.id).catch(() => {}); refresh(); }}>
                  ×
                </button>
              </div>
              <p className="mt-0.5 text-[11px] leading-snug text-muted-foreground">{m.content}</p>
            </div>
          ))}
        </div>
      </CardContent>
    </Card>
  );
}
