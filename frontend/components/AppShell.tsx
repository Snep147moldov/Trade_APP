"use client";

import { useCallback, useEffect, useMemo, useState, type ReactNode } from "react";
import { Dialog as DialogPrimitive } from "radix-ui";
import {
  ChevronDown,
  ChevronLeft,
  Ellipsis,
  LogOut,
  PanelLeft,
  X,
  type LucideIcon,
} from "lucide-react";

import { ThemeToggle } from "@/components/ThemeToggle";

export type NavLeaf = {
  key: string;
  label: string;
  icon: LucideIcon;
  badge?: number | null;
};

export type NavNode = NavLeaf & {
  /** раздел с подпунктами: сам не открывается, а разворачивается */
  children?: NavLeaf[];
};

const RAIL_KEY = "codnixy-rail";
const OPEN_KEY = "codnixy-nav-open";

type Props = {
  nav: NavNode[];
  /** ключи для нижней панели телефона — до них дотягивается большой палец */
  mobileKeys: string[];
  view: string;
  onView: (key: string) => void;
  brand: ReactNode;
  headerRight: ReactNode;
  sidebar?: ReactNode;
  banner?: ReactNode;
  /** страница сама держит высоту экрана и прокручивает свои области внутри —
   *  тогда общая прокрутка страницы не нужна */
  fill?: boolean;
  onLogout: () => void;
  children: ReactNode;
};

const flatten = (nav: NavNode[]): NavLeaf[] =>
  nav.flatMap((n) => (n.children?.length ? n.children : [n]));

export function AppShell({
  nav,
  mobileKeys,
  view,
  onView,
  brand,
  headerRight,
  sidebar,
  banner,
  fill = false,
  onLogout,
  children,
}: Props) {
  const [rail, setRail] = useState(false);
  const [sheet, setSheet] = useState(false);
  const [open, setOpen] = useState<string[]>([]);

  const leaves = useMemo(() => flatten(nav), [nav]);
  const active = leaves.find((n) => n.key === view);
  const activeParent = nav.find((n) => n.children?.some((c) => c.key === view));

  useEffect(() => {
    try {
      setRail(localStorage.getItem(RAIL_KEY) === "1");
      const saved = localStorage.getItem(OPEN_KEY);
      if (saved) setOpen(JSON.parse(saved));
    } catch {
      /* приватный режим */
    }
  }, []);

  const persistOpen = (next: string[]) => {
    setOpen(next);
    try {
      localStorage.setItem(OPEN_KEY, JSON.stringify(next));
    } catch {
      /* не критично */
    }
  };

  const toggleGroup = (key: string) =>
    persistOpen(open.includes(key) ? open.filter((k) => k !== key) : [...open, key]);

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

  const primary = mobileKeys
    .map((k) => leaves.find((n) => n.key === k))
    .filter((n): n is NavLeaf => Boolean(n));
  const restActive = !primary.some((n) => n.key === view);

  return (
    <div className="min-h-dvh bg-background">
      {/* ------------------------------------------------ сайдбар (десктоп) */}
      <aside
        className={`fixed inset-y-0 left-0 z-30 hidden shrink-0 flex-col border-r border-border bg-sidebar transition-[width] duration-200 lg:flex ${
          rail ? "w-[68px]" : "w-[248px]"
        }`}
      >
        <div
          className={`flex h-14 shrink-0 items-center gap-2 border-b border-border px-3 ${
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

        <nav className="scrollbar-thin min-h-0 flex-1 space-y-0.5 overflow-y-auto p-2">
          {nav.map((node) =>
            node.children?.length ? (
              <Group
                key={node.key}
                node={node}
                view={view}
                rail={rail}
                open={open.includes(node.key) || activeParent?.key === node.key}
                onToggle={() => toggleGroup(node.key)}
                onPick={pick}
              />
            ) : (
              <NavButton
                key={node.key}
                item={node}
                active={node.key === view}
                rail={rail}
                onClick={() => pick(node.key)}
              />
            ),
          )}

          {sidebar && !rail && (
            <div className="mt-3 border-t border-border pt-3">{sidebar}</div>
          )}
        </nav>

        <div
          className={`flex shrink-0 items-center gap-1 border-t border-border p-2 ${
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
      {/* В режиме fill колонка контента — настоящий flex во всю высоту экрана:
          шапка и полоса предупреждений забирают своё, остальное достаётся
          странице. Считать высоту через calc(100dvh - 3.5rem) нельзя — полоса
          предупреждений появляется и исчезает, и при ней страница уезжала за
          нижнюю границу, оставляя пустое место. */}
      <div
        className={`${rail ? "lg:pl-[68px]" : "lg:pl-[248px]"} transition-[padding] duration-200 ${
          fill ? "flex h-dvh flex-col" : ""
        }`}
      >
        <header
          className={`z-20 shrink-0 border-b border-border bg-background/80 backdrop-blur-xl ${
            fill ? "" : "sticky top-0"
          }`}
        >
          <div className="flex h-14 items-center gap-2 px-4 sm:px-6">
            <div className="shrink-0 lg:hidden">{brand}</div>
            <h2 className="hidden shrink-0 items-center gap-1.5 text-[15px] font-semibold tracking-tight lg:flex">
              {activeParent && (
                <>
                  <span className="font-normal text-muted-foreground">
                    {activeParent.label}
                  </span>
                  <span className="text-muted-foreground">/</span>
                </>
              )}
              {active?.label ?? ""}
            </h2>
            {/* Панель действий шире экрана телефона: справочные бейджи прячутся,
                остальное прокручивается пальцем, а не обрезается. */}
            <div className="no-scrollbar ml-auto flex min-w-0 flex-1 items-center gap-1 overflow-x-auto pl-1 sm:justify-end sm:gap-2">
              {headerRight}
            </div>
          </div>
        </header>

        <div className="shrink-0">{banner}</div>

        <main
          className={
            fill
              ? // снизу оставлено место под нижнюю панель телефона; на десктопе
                // её нет, поэтому отступ там обычный
                "mx-auto w-full min-h-0 max-w-[1500px] flex-1 px-4 pb-[4.75rem] pt-3 sm:px-6 lg:pb-4"
              : "mx-auto max-w-[1500px] px-4 pb-28 pt-4 sm:px-6 sm:pt-6 lg:pb-10"
          }
        >
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
          <button
            type="button"
            onClick={() => setSheet(true)}
            className={`flex flex-1 flex-col items-center gap-1 py-2 text-[10px] transition-colors ${
              restActive ? "text-brand" : "text-muted-foreground"
            }`}
          >
            <Ellipsis className="h-5 w-5" />
            <span className="truncate px-0.5">Ещё</span>
          </button>
        </div>
      </nav>

      {/* ------------------------------------------ «Ещё»: панель снизу */}
      <DialogPrimitive.Root open={sheet} onOpenChange={setSheet}>
        <DialogPrimitive.Portal>
          <DialogPrimitive.Overlay className="fixed inset-0 z-40 bg-foreground/20 backdrop-blur-[2px] data-open:animate-in data-open:fade-in-0 data-closed:animate-out data-closed:fade-out-0 lg:hidden" />
          <DialogPrimitive.Content className="pb-safe fixed inset-x-0 bottom-0 z-50 max-h-[88dvh] overflow-y-auto rounded-t-3xl border-t border-border bg-card p-4 shadow-pop data-open:animate-in data-open:slide-in-from-bottom data-closed:animate-out data-closed:slide-out-to-bottom lg:hidden">
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
              Все разделы приложения и список избранных инструментов
            </DialogPrimitive.Description>

            <div className="space-y-3">
              {nav.map((node) => (
                <div key={node.key}>
                  {node.children?.length && (
                    <p className="mb-1.5 px-1 text-[11px] font-medium uppercase tracking-wide text-muted-foreground">
                      {node.label}
                    </p>
                  )}
                  <div className="grid grid-cols-2 gap-2">
                    {(node.children?.length ? node.children : [node]).map((leaf) => (
                      <button
                        key={leaf.key}
                        type="button"
                        onClick={() => pick(leaf.key)}
                        className={`flex items-center gap-2.5 rounded-2xl px-3 py-3 text-left text-sm transition-colors ${
                          leaf.key === view
                            ? "bg-brand font-medium text-white shadow-sm"
                            : "bg-muted text-foreground"
                        }`}
                      >
                        <leaf.icon className="h-4 w-4 shrink-0" />
                        <span className="truncate">{leaf.label}</span>
                      </button>
                    ))}
                  </div>
                </div>
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

function Group({
  node,
  view,
  rail,
  open,
  onToggle,
  onPick,
}: {
  node: NavNode;
  view: string;
  rail: boolean;
  open: boolean;
  onToggle: () => void;
  onPick: (key: string) => void;
}) {
  const hasActive = node.children?.some((c) => c.key === view) ?? false;

  // в узком рельсе подписи нет: разворачивать нечего, показываем иконки
  // подпунктов подряд, отделяя группы чертой
  if (rail) {
    return (
      <div className="mb-1 space-y-0.5 border-b border-border pb-1 last:border-0">
        {node.children?.map((leaf) => (
          <NavButton
            key={leaf.key}
            item={leaf}
            active={leaf.key === view}
            rail
            onClick={() => onPick(leaf.key)}
          />
        ))}
      </div>
    );
  }

  return (
    <div>
      <button
        type="button"
        onClick={onToggle}
        aria-expanded={open}
        className={`flex h-10 w-full items-center gap-3 rounded-xl px-3 text-sm transition-colors ${
          hasActive && !open
            ? "font-medium text-foreground"
            : "text-muted-foreground hover:bg-accent hover:text-foreground"
        }`}
      >
        <node.icon className="h-[18px] w-[18px] shrink-0" />
        <span className="min-w-0 flex-1 truncate text-left">{node.label}</span>
        <ChevronDown
          className={`h-3.5 w-3.5 shrink-0 transition-transform ${open ? "" : "-rotate-90"}`}
        />
      </button>
      {open && (
        <div className="ml-[18px] space-y-0.5 border-l border-border py-0.5 pl-2">
          {node.children?.map((leaf) => (
            <button
              key={leaf.key}
              type="button"
              onClick={() => onPick(leaf.key)}
              aria-current={leaf.key === view ? "page" : undefined}
              className={`flex h-9 w-full items-center gap-2.5 rounded-lg px-2.5 text-[13px] transition-colors ${
                leaf.key === view
                  ? "bg-brand font-medium text-white shadow-sm"
                  : "text-muted-foreground hover:bg-accent hover:text-foreground"
              }`}
            >
              <span className="min-w-0 flex-1 truncate text-left">{leaf.label}</span>
              {leaf.badge != null && leaf.badge > 0 && (
                <span className="shrink-0 rounded-full bg-muted px-1.5 py-0.5 text-[10px] font-medium tabular-nums text-muted-foreground">
                  {leaf.badge > 99 ? "99+" : leaf.badge}
                </span>
              )}
            </button>
          ))}
        </div>
      )}
    </div>
  );
}

function NavButton({
  item,
  active,
  rail,
  onClick,
}: {
  item: NavLeaf;
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
      className={`group relative flex h-10 w-full items-center gap-3 rounded-xl text-sm transition-colors ${
        rail ? "justify-center px-0" : "px-3"
      } ${
        active
          ? "bg-brand font-medium text-white shadow-sm"
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
  item: NavLeaf;
  active: boolean;
  onClick: () => void;
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      aria-current={active ? "page" : undefined}
      className={`relative flex flex-1 flex-col items-center gap-1 py-2 text-[10px] transition-colors ${
        active ? "text-brand" : "text-muted-foreground"
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
