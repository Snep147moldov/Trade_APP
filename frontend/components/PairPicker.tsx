"use client";

import { useMemo, useState } from "react";
import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { api, type InstrumentsResult } from "@/lib/api";

export function PairPicker({
  data,
  watchlist,
  onSave,
  onCatalogChange,
}: {
  data: InstrumentsResult | null;
  watchlist: string[];
  onSave: (watchlist: string[]) => Promise<void>;
  onCatalogChange: () => void;
}) {
  const [open, setOpen] = useState(false);
  const [query, setQuery] = useState("");
  const [category, setCategory] = useState<string>("forex");
  const [selected, setSelected] = useState<string[]>(watchlist);
  const [saving, setSaving] = useState(false);
  const [adding, setAdding] = useState(false);
  const [addMsg, setAddMsg] = useState<string | null>(null);

  const categories = data?.categories ?? [];
  const items = useMemo(() => {
    const q = query.toUpperCase().replace("/", "_");
    if (q) {
      // search across all categories
      return categories.flatMap((c) =>
        c.instruments.filter(
          (i) => i.symbol.includes(q) || i.name.toUpperCase().includes(query.toUpperCase())
        )
      );
    }
    return categories.find((c) => c.key === category)?.instruments ?? [];
  }, [categories, category, query]);

  const cleanTicker = query.toUpperCase().replace("/", "").replace("_USD", "").trim();
  const canAddCustom =
    query.length >= 1 &&
    items.length === 0 &&
    /^[A-Z0-9.]{1,10}$/.test(cleanTicker);

  const toggle = (symbol: string) =>
    setSelected((s) => (s.includes(symbol) ? s.filter((x) => x !== symbol) : [...s, symbol]));

  const addCustom = async (cat: "stocks" | "crypto") => {
    setAdding(true);
    setAddMsg(null);
    try {
      const r = await api.addCustomInstrument(cleanTicker, cat);
      setSelected((s) => (s.includes(r.symbol) ? s : [...s, r.symbol]));
      setAddMsg(`✅ ${r.symbol.replace("_", "/")} добавлен и выбран.`);
      setQuery("");
      onCatalogChange();
    } catch (e) {
      setAddMsg(`❌ ${e instanceof Error ? e.message.replace(/^\d+\s*/, "").slice(0, 100) : "ошибка"}`);
    }
    setAdding(false);
  };

  const save = async () => {
    setSaving(true);
    await onSave(selected);
    setSaving(false);
    setOpen(false);
  };

  return (
    <Dialog
      open={open}
      onOpenChange={(o) => {
        setOpen(o);
        if (o) {
          setSelected(watchlist);
          setAddMsg(null);
        }
      }}
    >
      <DialogTrigger asChild>
        <Button variant="outline" size="sm" className="w-full rounded-xl">
          Выбрать инструменты
        </Button>
      </DialogTrigger>
      <DialogContent className="rounded-2xl sm:max-w-[560px]">
        <DialogHeader>
          <DialogTitle className="tracking-tight">Все рынки</DialogTitle>
          <DialogDescription>
            ~390 инструментов: форекс, металлы, индексы, энергия, фьючерсы,
            акции, ETF, крипто. Нет в списке — добавьте свой тикер.
            Выбрано: {selected.length}
          </DialogDescription>
        </DialogHeader>
        <Input
          placeholder="Поиск: NVDA, золото, DOGE, нефть… или любой тикер"
          className="rounded-xl"
          value={query}
          onChange={(e) => setQuery(e.target.value)}
        />
        {!query && (
          <div className="flex flex-wrap gap-1.5">
            {categories.map((c) => (
              <button
                key={c.key}
                onClick={() => setCategory(c.key)}
                className={`rounded-full px-3 py-1 text-xs transition-colors ${
                  c.key === category
                    ? "bg-[#0a84ff] font-medium text-white"
                    : "bg-muted/60 text-muted-foreground hover:bg-muted"
                }`}
              >
                {c.label}
                <span className="ml-1 opacity-60">{c.instruments.length}</span>
              </button>
            ))}
          </div>
        )}
        <div className="grid max-h-[300px] grid-cols-2 gap-1.5 overflow-y-auto py-1">
          {items.map((it) => {
            const active = selected.includes(it.symbol);
            return (
              <button
                key={it.symbol}
                onClick={() => toggle(it.symbol)}
                className={`flex items-center justify-between rounded-xl px-3 py-1.5 text-left text-sm transition-colors ${
                  active
                    ? "bg-[#0a84ff] font-medium text-white"
                    : "bg-muted/60 text-muted-foreground hover:bg-muted"
                }`}
              >
                <span className="truncate">{it.name}</span>
                <span className={`ml-2 text-[10px] ${active ? "text-white/70" : "text-muted-foreground/60"}`}>
                  {it.symbol.replace("_", "/")}
                </span>
              </button>
            );
          })}
          {canAddCustom && (
            <div className="col-span-2 rounded-xl bg-muted/40 p-3 text-center">
              <p className="mb-2 text-xs text-muted-foreground">
                «{cleanTicker}» нет в каталоге — добавить как:
              </p>
              <div className="flex justify-center gap-2">
                <Button variant="outline" size="sm" className="rounded-xl"
                        disabled={adding} onClick={() => addCustom("stocks")}>
                  Акция
                </Button>
                <Button variant="outline" size="sm" className="rounded-xl"
                        disabled={adding} onClick={() => addCustom("crypto")}>
                  Криптовалюта
                </Button>
              </div>
            </div>
          )}
        </div>
        {addMsg && <p className="text-center text-xs text-muted-foreground">{addMsg}</p>}
        <Button className="w-full rounded-xl" onClick={save} disabled={saving}>
          {saving ? "Сохраняю…" : "Сохранить в «Избранное»"}
        </Button>
      </DialogContent>
    </Dialog>
  );
}
