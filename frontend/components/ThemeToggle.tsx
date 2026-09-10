"use client";

import { useCallback, useEffect, useState } from "react";
import { Monitor, Moon, Sun } from "lucide-react";

export type Theme = "light" | "dark" | "system";

const KEY = "codnixy-theme";
const ORDER: Theme[] = ["light", "dark", "system"];

function apply(theme: Theme) {
  const dark =
    theme === "dark" ||
    (theme === "system" &&
      window.matchMedia("(prefers-color-scheme: dark)").matches);
  document.documentElement.setAttribute("data-theme", dark ? "dark" : "light");
}

/** Тему держит атрибут на <html>: его выставляет скрипт в layout.tsx до первой
 *  отрисовки. Здесь только переключение и подписка на смену системной темы. */
export function useTheme() {
  // Ленивый инициализатор читает тот же ключ, что и скрипт в <head>, поэтому
  // состояние React и DOM совпадают с самого начала и гидратация не спорит.
  const [theme, setThemeState] = useState<Theme>(() => {
    if (typeof window === "undefined") return "system";
    return (localStorage.getItem(KEY) as Theme) || "system";
  });

  const setTheme = useCallback((next: Theme) => {
    setThemeState(next);
    try {
      localStorage.setItem(KEY, next);
    } catch {
      /* приватный режим — тема просто не переживёт перезагрузку */
    }
    apply(next);
  }, []);

  useEffect(() => {
    if (theme !== "system") return;
    const mq = window.matchMedia("(prefers-color-scheme: dark)");
    const onChange = () => apply("system");
    mq.addEventListener("change", onChange);
    return () => mq.removeEventListener("change", onChange);
  }, [theme]);

  return { theme, setTheme };
}

/** Читает фактический цвет токена. Нужен для lightweight-charts: график
 *  рисуется на canvas и CSS-переменную не понимает, ему нужно значение. */
export function cssColor(token: string, fallback = "#8e8e93"): string {
  if (typeof window === "undefined") return fallback;
  const v = getComputedStyle(document.documentElement)
    .getPropertyValue(token)
    .trim();
  return v || fallback;
}

/** true, когда сейчас тёмная тема — по атрибуту, а не по настройке, потому что
 *  "system" может быть и той, и другой. */
export function useIsDark() {
  const { theme } = useTheme();
  const [dark, setDark] = useState(false);
  useEffect(() => {
    const read = () =>
      setDark(document.documentElement.getAttribute("data-theme") === "dark");
    read();
    const mo = new MutationObserver(read);
    mo.observe(document.documentElement, {
      attributes: true,
      attributeFilter: ["data-theme"],
    });
    return () => mo.disconnect();
  }, [theme]);
  return dark;
}

const LABEL: Record<Theme, string> = {
  light: "Светлая тема",
  dark: "Тёмная тема",
  system: "Как в системе",
};

export function ThemeChoice() {
  const { theme, setTheme } = useTheme();
  const [mounted, setMounted] = useState(false);
  useEffect(() => setMounted(true), []);
  const items: { key: Theme; label: string; icon: typeof Sun }[] = [
    { key: "light", label: "Светлая", icon: Sun },
    { key: "dark", label: "Тёмная", icon: Moon },
    { key: "system", label: "Система", icon: Monitor },
  ];
  return (
    <div className="glass grid grid-cols-3 gap-1 rounded-2xl p-1">
      {items.map((it) => (
        <button
          key={it.key}
          type="button"
          onClick={() => setTheme(it.key)}
          className={`flex flex-col items-center gap-1 rounded-xl py-2.5 text-[13px] sm:text-[11px] transition-all duration-200 active:scale-95 ${
            mounted && theme === it.key
              ? "bg-brand font-medium text-white shadow-sm"
              : "text-muted-foreground hover:bg-accent hover:text-foreground"
          }`}
        >
          <it.icon className="h-4 w-4" />
          {it.label}
        </button>
      ))}
    </div>
  );
}

export function ThemeToggle({ className = "" }: { className?: string }) {
  const { theme, setTheme } = useTheme();
  const [mounted, setMounted] = useState(false);
  useEffect(() => setMounted(true), []);

  const Icon = theme === "dark" ? Moon : theme === "light" ? Sun : Monitor;
  const next = ORDER[(ORDER.indexOf(theme) + 1) % ORDER.length];

  return (
    <button
      type="button"
      onClick={() => setTheme(next)}
      title={`${LABEL[theme]} — нажмите для «${LABEL[next].toLowerCase()}»`}
      aria-label={LABEL[theme]}
      className={`inline-flex h-9 w-9 items-center justify-center rounded-xl text-muted-foreground transition-colors hover:bg-accent hover:text-foreground ${className}`}
    >
      {/* до монтирования иконка неизвестна: значение лежит в localStorage,
          на сервере его нет. Рисуем пустое место такого же размера, чтобы
          шапка не дёргалась. */}
      {mounted ? <Icon className="h-4 w-4" /> : <span className="h-4 w-4" />}
    </button>
  );
}
