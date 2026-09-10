"use client";

import { forwardRef, type ReactNode } from "react";
import { ChevronRight, type LucideIcon } from "lucide-react";

/** Плитка настройки — вид из образца: иконка в кружке, название, под ним
 *  подсказка с текущим значением. Отдаётся диалогу как `trigger`, поэтому
 *  должна пробрасывать ref и обработчики: Radix вешает их на потомка. */
export const SettingsCard = forwardRef<
  HTMLButtonElement,
  {
    icon: LucideIcon;
    label: string;
    hint?: string;
    tone?: "brand" | "neutral";
  } & React.ButtonHTMLAttributes<HTMLButtonElement>
>(function SettingsCard({ icon: Icon, label, hint, tone = "neutral", ...props }, ref) {
  return (
    <button
      ref={ref}
      type="button"
      {...props}
      className="glass group flex w-full items-start gap-3 rounded-2xl p-3 text-left transition-all duration-200 hover:-translate-y-0.5 hover:shadow-pop"
    >
      <span
        className={`flex h-9 w-9 shrink-0 items-center justify-center rounded-xl transition-colors ${
          tone === "brand"
            ? "bg-brand text-white"
            : "bg-brand/10 text-brand-ink group-hover:bg-brand group-hover:text-white"
        }`}
      >
        <Icon className="h-4 w-4" />
      </span>
      <span className="min-w-0 flex-1">
        <span className="flex items-center gap-1 text-[13px] font-medium">
          <span className="truncate">{label}</span>
          <ChevronRight className="h-3 w-3 shrink-0 text-muted-foreground transition-transform group-hover:translate-x-0.5" />
        </span>
        {hint && (
          <span className="mt-0.5 block truncate text-[11px] text-muted-foreground">
            {hint}
          </span>
        )}
      </span>
    </button>
  );
});

export function SettingsSection({
  title,
  children,
}: {
  title: string;
  children: ReactNode;
}) {
  return (
    <div>
      <p className="mb-2 px-1 text-[11px] font-medium uppercase tracking-wide text-muted-foreground">
        {title}
      </p>
      <div className="grid grid-cols-2 gap-2">{children}</div>
    </div>
  );
}
