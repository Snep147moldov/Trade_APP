"use client";

import { useCallback, useEffect, useState, type ReactNode } from "react";
import { Dialog as DialogPrimitive } from "radix-ui";
import {
  ChevronLeft,
  Ellipsis,
  LogOut,
  PanelLeft,
  X,
  type LucideIcon,
} from "lucide-react";

import { ThemeToggle } from "@/components/ThemeToggle";

export type NavItem = {
  key: string;
  label: string;
  icon: LucideIcon;
  /** число рядом с пунктом: открытые сигналы, непрочитанные и т.п. */
  badge?: number | null;
};

/** Сколько пунктов помещается в нижнюю панель телефона. Пятое место занимает
 *  «Ещё»: четыре иконки шириной по 25% ещё читаются на 360px, пять — уже нет. */
const MOBILE_SLOTS = 4;

const RAIL_KEY = "codnixy-rail";

type Props = {
  nav: NavItem[];
  view: string;
  onView: (key: string) => void;
  /** логотип и название — в шапке сайдбара */
  brand: ReactNode;
  /** статус-бейджи и кнопки диалогов — справа в шапке */
  headerRight: ReactNode;
  /** избранное и подборки — под навигацией, прокручивается отдельно */
  sidebar?: ReactNode;
  /** полоса предупреждений над контентом */
  banner?: ReactNode;
  onLogout: () => void;
  children: ReactNode;
};

export function AppShell({
  nav,
  view,
  onView,
  brand,
  headerRight,
  sidebar,
  banner,
  onLogout,
  children,
}: Props) {
  const [rail, setRail] = useState(false);
  const [sheet, setSheet] = useState(false);

  useEffect(() => {
    try {
      setRail(localStorage.getItem(RAIL_KEY) === "1");
    } catch {
      /* приватный режим */
    }
  }, []);

  const toggleRail = useCallback(() => {
    setRail((v) => {
      try {
        localStorage.setItem(RAIL_KEY, v ? "0" : "1");
      } catch {
        /* не критично */
      }
      return !v;
    });
  }, []);

  const pick = useCallback(
    (key: string) => {
      onView(key);
      setSheet(false);
    },
    [onView],
  );

  const active = nav.find((n) => n.key === view);
  const primary = nav.slice(0, MOBILE_SLOTS);
  const rest = nav.slice(MOBILE_SLOTS);
  // «Ещё» подсвечивается, когда открыт раздел, который в панель не поместился —
  // иначе на телефоне не видно, где ты находишься
  const restActive = rest.some((n) => n.key === view);

  return (
    <div className="min-h-screen bg-background">
      {/* ------------------------------------------------ сайдбар (десктоп) */}
      <aside
        className={`fixed inset-y-0 left-0 z-30 hidden shrink-0 flex-col border-r border-border bg-sidebar transition-[width] duration-200 lg:flex ${
          rail ? "w-[68px]" : "w-[248px]"
        }`}
      >
        <div
          className={`flex h-14 items-center gap-2 border-b border-border px-3 ${
            rail ? "justify-center" : ""
          }`}
        >
          {rail ? (
            <button
              type="button"
              onClick={toggleRail}
              title="Развернуть меню"
              className="inline-flex h-9 w-9 items-center justify-center rounded-xl text-muted-foreground transition-colors hover:bg-accent hover:text-foreground"
            >
              <PanelLeft className="h-4 w-4" />
            </button>
          ) : (
            <>
              <div className="min-w-0 flex-1">{brand}</div>
              <button
                type="button"
                onClick={toggleRail}
                title="Свернуть меню"
                className="inline-flex h-8 w-8 shrink-0 items-center justify-center rounded-lg text-muted-foreground transition-colors hover:bg-accent hover:text-foreground"
              >
                <ChevronLeft className="h-4 w-4" />
              </button>
            </>
          )}
        </div>

        <nav className="flex flex-col gap-0.5 p-2">
          {nav.map((item) => (
            <NavButton
              key={item.key}
              item={item}
              active={item.key === view}
              rail={rail}
              onClick={() => pick(item.key)}
            />
          ))}
        </nav>

        {sidebar && !rail && (
          <div className="scrollbar-thin min-h-0 flex-1 overflow-y-auto border-t border-border px-2 py-3">
            {sidebar}
          </div>
        )}
        {rail && <div className="flex-1" />}

        <div
          className={`flex items-center gap-1 border-t border-border p-2 ${
            rail ? "flex-col" : ""
          }`}
        >
          <ThemeToggle />
          <button
            type="button"
            onClick={onLogout}
            title="Выйти"
            className={`inline-flex h-9 items-center gap-2 rounded-xl px-3 text-sm text-muted-foreground transition-colors hover:bg-accent hover:text-foreground ${
              rail ? "w-9 justify-center px-0" : "flex-1 justify-start"
            }`}
          >
            <LogOut className="h-4 w-4 shrink-0" />
            {!rail && <span>Выйти</span>}
          </button>
        </div>
      </aside>

      {/* ------------------------------------------------------- контент */}
      <div className={`${rail ? "lg:pl-[68px]" : "lg:pl-[248px]"} transition-[padding] duration-200`}>
        <header className="sticky top-0 z-20 border-b border-border bg-background/80 backdrop-blur-xl">
          <div className="flex h-14 items-center gap-2 px-4 sm:px-6">
            {/* на телефоне логотип живёт в шапке: сайдбара там нет */}
            <div className="shrink-0 lg:hidden">{brand}</div>
            <h2 className="hidden shrink-0 text-[15px] font-semibold tracking-tight lg:block">
              {active?.label ?? ""}
            </h2>
            {/* Панель действий шире экрана телефона: восемь кнопок и бейджей в
                390px не помещаются, а прятать их некуда — диалоги нужны все.
                Поэтому она прокручивается пальцем, а не обрезается. */}
            <div className="no-scrollbar ml-auto flex min-w-0 flex-1 items-center gap-1 overflow-x-auto pl-1 sm:gap-2 sm:justify-end">
              {headerRight}
            </div>
          </div>
        </header>

        {banner}

        {/* нижняя панель перекрывает контент — компенсируем её высотой отступа */}
        <main className="mx-auto max-w-[1500px] px-4 pb-28 pt-4 sm:px-6 sm:pt-6 lg:pb-10">
          {children}
        </main>
      </div>

      {/* ------------------------------------------- нижняя панель (телефон) */}
      <nav className="pb-safe fixed inset-x-0 bottom-0 z-30 border-t border-border bg-background/95 backdrop-blur-xl lg:hidden">
        <div className="flex items-stretch">
          {primary.map((item) => (
            <TabButton
              key={item.key}
              item={item}
              active={item.key === view}
              onClick={() => pick(item.key)}
            />
          ))}
          {rest.length > 0 && (
            <button
              type="button"
              onClick={() => setSheet(true)}
              className={`flex flex-1 flex-col items-center gap-1 py-2 text-[10px] transition-colors ${
                restActive ? "text-brand-ink" : "text-muted-foreground"
              }`}
            >
              <Ellipsis className="h-5 w-5" />
              <span className="truncate px-0.5">Ещё</span>
            </button>
          )}
        </div>
      </nav>

      {/* ------------------------------------------ «Ещё»: панель снизу */}
      <DialogPrimitive.Root open={sheet} onOpenChange={setSheet}>
        <DialogPrimitive.Portal>
          <DialogPrimitive.Overlay className="fixed inset-0 z-40 bg-foreground/20 backdrop-blur-[2px] data-open:animate-in data-open:fade-in-0 data-closed:animate-out data-closed:fade-out-0 lg:hidden" />
          <DialogPrimitive.Content className="pb-safe fixed inset-x-0 bottom-0 z-50 max-h-[85vh] overflow-y-auto rounded-t-3xl border-t border-border bg-card p-4 shadow-pop data-open:animate-in data-open:slide-in-from-bottom data-closed:animate-out data-closed:slide-out-to-bottom lg:hidden">
            <div className="mx-auto mb-3 h-1 w-10 rounded-full bg-border" />
            <div className="mb-3 flex items-center justify-between">
              <DialogPrimitive.Title className="text-base font-semibold tracking-tight">
                Разделы
              </DialogPrimitive.Title>
              <DialogPrimitive.Close className="inline-flex h-8 w-8 items-center justify-center rounded-lg text-muted-foreground transition-colors hover:bg-accent">
                <X className="h-4 w-4" />
              </DialogPrimitive.Close>
            </div>
            <DialogPrimitive.Description className="sr-only">
              Остальные разделы приложения и список избранных инструментов
            </DialogPrimitive.Description>

            <div className="grid grid-cols-2 gap-2">
              {rest.map((item) => (
                <button
                  key={item.key}
                  type="button"
                  onClick={() => pick(item.key)}
                  className={`flex items-center gap-2.5 rounded-2xl px-3 py-3 text-left text-sm transition-colors ${
                    item.key === view
                      ? "bg-brand/10 font-medium text-brand-ink"
                      : "bg-muted text-foreground"
                  }`}
                >
                  <item.icon className="h-4 w-4 shrink-0" />
                  <span className="truncate">{item.label}</span>
                </button>
              ))}
            </div>

            {sidebar && (
              <div className="mt-4 border-t border-border pt-4">{sidebar}</div>
            )}

            <div className="mt-4 flex items-center gap-2 border-t border-border pt-3">
              <ThemeToggle />
              <button
                type="button"
                onClick={onLogout}
                className="inline-flex h-9 flex-1 items-center justify-center gap-2 rounded-xl bg-muted text-sm text-muted-foreground transition-colors hover:text-foreground"
              >
                <LogOut className="h-4 w-4" /> Выйти
              </button>
            </div>
          </DialogPrimitive.Content>
        </DialogPrimitive.Portal>
      </DialogPrimitive.Root>
    </div>
  );
}

function NavButton({
  item,
  active,
  rail,
  onClick,
}: {
  item: NavItem;
  active: boolean;
  rail: boolean;
  onClick: () => void;
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      title={rail ? item.label : undefined}
      aria-current={active ? "page" : undefined}
      className={`group relative flex h-10 items-center gap-3 rounded-xl text-sm transition-colors ${
        rail ? "justify-center px-0" : "px-3"
      } ${
        active
          ? "bg-brand/10 font-medium text-brand-ink"
          : "text-muted-foreground hover:bg-accent hover:text-foreground"
      }`}
    >
      <item.icon className="h-[18px] w-[18px] shrink-0" />
      {!rail && <span className="min-w-0 flex-1 truncate text-left">{item.label}</span>}
      {item.badge != null && item.badge > 0 && (
        <span
          className={`shrink-0 rounded-full text-[10px] font-medium tabular-nums ${
            rail
              ? "absolute right-2 top-1.5 h-4 min-w-4 px-1 leading-4"
              : "px-1.5 py-0.5"
          } ${active ? "bg-brand text-white" : "bg-muted text-muted-foreground"}`}
        >
          {item.badge > 99 ? "99+" : item.badge}
        </span>
      )}
    </button>
  );
}

function TabButton({
  item,
  active,
  onClick,
}: {
  item: NavItem;
  active: boolean;
  onClick: () => void;
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      aria-current={active ? "page" : undefined}
      className={`relative flex flex-1 flex-col items-center gap-1 py-2 text-[10px] transition-colors ${
        active ? "text-brand-ink" : "text-muted-foreground"
      }`}
    >
      <span className="relative">
        <item.icon className="h-5 w-5" />
        {item.badge != null && item.badge > 0 && (
          <span className="absolute -right-2 -top-1 h-3.5 min-w-3.5 rounded-full bg-brand px-1 text-[9px] font-medium leading-3.5 text-white tabular-nums">
            {item.badge > 9 ? "9+" : item.badge}
          </span>
        )}
      </span>
      <span className="truncate px-0.5">{item.label}</span>
    </button>
  );
}
