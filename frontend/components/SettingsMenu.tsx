"use client";

import { useState, type ReactNode } from "react";
import { Popover as PopoverPrimitive } from "radix-ui";
import { Settings2 } from "lucide-react";

/** Одна точка входа во всё, что связано с настройками.
 *
 *  Раньше «Подключения», «Алерты», «Админ» и «Аккаунт» стояли отдельными
 *  кнопками в шапке: восемь элементов не помещались в 390px, а на десктопе
 *  занимали половину строки. Теперь они собраны здесь, а снаружи осталась
 *  только «Стратегия» — единственное, что меняют по ходу торговли.
 *
 *  Диалоги рендерятся как есть: их кнопки-триггеры превращаются в строки меню
 *  через селектор потомков, чтобы не переписывать четыре компонента. */
export function SettingsMenu({ children }: { children: ReactNode }) {
  const [open, setOpen] = useState(false);

  return (
    <PopoverPrimitive.Root open={open} onOpenChange={setOpen}>
      <PopoverPrimitive.Trigger asChild>
        <button
          type="button"
          title="Настройки"
          aria-label="Настройки"
          className={`inline-flex h-9 w-9 shrink-0 items-center justify-center rounded-xl transition-colors ${
            open
              ? "bg-brand text-white"
              : "text-muted-foreground hover:bg-accent hover:text-foreground"
          }`}
        >
          <Settings2 className="h-4 w-4" />
        </button>
      </PopoverPrimitive.Trigger>

      <PopoverPrimitive.Portal>
        <PopoverPrimitive.Content
          align="end"
          sideOffset={8}
          className="z-50 w-60 rounded-2xl border border-border bg-popover p-1.5 shadow-pop data-open:animate-in data-open:fade-in-0 data-open:zoom-in-95 data-closed:animate-out data-closed:fade-out-0"
        >
          <p className="px-2.5 pb-1 pt-1.5 text-[11px] font-medium uppercase tracking-wide text-muted-foreground">
            Настройки
          </p>
          {/* кнопки диалогов приводим к виду строк меню, не трогая сами диалоги */}
          <div
            className="flex flex-col gap-0.5 [&_button]:h-9 [&_button]:w-full [&_button]:justify-start [&_button]:rounded-xl [&_button]:border-0 [&_button]:bg-transparent [&_button]:px-2.5 [&_button]:text-sm [&_button]:font-normal [&_button]:shadow-none hover:[&_button]:bg-accent"
            onClick={() => setOpen(false)}
          >
            {children}
          </div>
        </PopoverPrimitive.Content>
      </PopoverPrimitive.Portal>
    </PopoverPrimitive.Root>
  );
}
