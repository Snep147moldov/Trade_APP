"use client";

import {
  useCallback,
  useEffect,
  useMemo,
  useRef,
  useState,
  type ReactNode,
} from "react";
import { Dialog as DialogPrimitive } from "radix-ui";
import {
  ChevronLeft,
  ChevronRight,
  Ellipsis,
  LogOut,
  Menu,
  PanelLeft,
  Settings2,
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
  /** раздел с подпунктами: открывается панелью справа от меню */
  children?: NavLeaf[];
};

const RAIL_KEY = "codnixy-rail";

type Props = {
  nav: NavNode[];
  /** ключи для нижней панели телефона — до них дотягивается большой палец */
  mobileKeys: string[];
  view: string;
  onView: (key: string) => void;
  brand: ReactNode;
  headerRight: ReactNode;
  /** содержимое панели настроек: открывается бургером слева */
  settings?: ReactNode;
  /** избранное и подборки */
  sidebar?: ReactNode;
  banner?: ReactNode;
  /** плавающая кнопка основного действия */
  fab?: ReactNode;
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
  settings,
  sidebar,
  banner,
  fab,
  onLogout,
  children,
}: Props) {
  const [rail, setRail] = useState(false);
  const [sheet, setSheet] = useState(false);
  const [prefs, setPrefs] = useState(false);
  // ключ раздела + вертикальная позиция кнопки, которая его открыла: панель
  // должна встать вровень с ней, а не в начале меню
  const [flyout, setFlyout] = useState<{ key: string; top: number } | null>(null);
  const [scrolled, setScrolled] = useState(false);
  const asideRef = useRef<HTMLElement>(null);

  const leaves = useMemo(() => flatten(nav), [nav]);
  const active = leaves.find((n) => n.key === view);
  const activeParent = nav.find((n) => n.children?.some((c) => c.key === view));

  useEffect(() => {
    try {
      setRail(localStorage.getItem(RAIL_KEY) === "1");
    } catch {
      /* приватный режим */
    }
  }, []);

  // выпадающая вправо панель закрывается по клику мимо неё и по Escape:
  // она перекрывает содержимое, и запертым в ней оставаться нельзя
  useEffect(() => {
    if (!flyout) return;
    const onDown = (e: MouseEvent) => {
      if (!asideRef.current?.contains(e.target as Node)) setFlyout(null);
    };
    const onKey = (e: KeyboardEvent) => e.key === "Escape" && setFlyout(null);
    document.addEventListener("mousedown", onDown);
    document.addEventListener("keydown", onKey);
    return () => {
      document.removeEventListener("mousedown", onDown);
      document.removeEventListener("keydown", onKey);
    };
  }, [flyout]);

  const toggleRail = useCallback(() => {
    setFlyout(null);
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
      setFlyout(null);
    },
    [onView],
  );

  const primary = mobileKeys
    .map((k) => leaves.find((n) => n.key === k))
    .filter((n): n is NavLeaf => Boolean(n));
  const restActive = !primary.some((n) => n.key === view);
  const openNode = nav.find((n) => n.key === flyout?.key);
  // не даём панели уехать за нижний край: если пунктов много, поднимаем её
  const flyoutTop =
    flyout && openNode?.children
      ? Math.max(
          8,
          Math.min(
            flyout.top,
            (typeof window === "undefined" ? 900 : window.innerHeight) -
              (openNode.children.length * 44 + 60),
          ),
        )
      : 0;

  return (
    <div className="min-h-dvh">
      {/* ------------------------------------------------ меню (десктоп) */}
      <aside
        ref={asideRef}
        className="fixed inset-y-0 left-0 z-30 hidden lg:block"
      >
        <div
          className={`flex h-full flex-col border-r bg-sidebar/70 backdrop-blur-2xl transition-[width] duration-300 ${
            rail ? "w-[68px]" : "w-[248px]"
          }`}
          style={{ borderColor: "var(--glass-edge)" }}
        >
          <div
            className={`flex h-14 shrink-0 items-center gap-2 px-3 ${
              rail ? "justify-center" : ""
            }`}
          >
            {rail ? (
              <button
                type="button"
                onClick={toggleRail}
                title="Развернуть меню"
                className="inline-flex h-9 w-9 items-center justify-center rounded-xl text-muted-foreground transition-all hover:bg-accent hover:text-foreground active:scale-95"
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
                  className="inline-flex h-8 w-8 shrink-0 items-center justify-center rounded-lg text-muted-foreground transition-all hover:bg-accent hover:text-foreground active:scale-95"
                >
                  <ChevronLeft className="h-4 w-4" />
                </button>
              </>
            )}
          </div>

          <nav className="scrollbar-thin min-h-0 flex-1 space-y-0.5 overflow-y-auto p-2">
            {nav.map((node) => (
              <NavButton
                key={node.key}
                item={node}
                active={
                  node.key === view || (activeParent?.key === node.key && !flyout)
                }
                highlighted={flyout?.key === node.key}
                rail={rail}
                hasChildren={Boolean(node.children?.length)}
                onClick={(e) => {
                  if (!node.children?.length) {
                    pick(node.key);
                    return;
                  }
                  const top = e.currentTarget.getBoundingClientRect().top;
                  setFlyout((f) => (f?.key === node.key ? null : { key: node.key, top }));
                }}
              />
            ))}

            {settings && (
              <button
                type="button"
                onClick={() => {
                  setFlyout(null);
                  setPrefs(true);
                }}
                title={rail ? "Настройки" : undefined}
                className={`flex h-10 w-full items-center gap-3 rounded-xl text-sm text-muted-foreground transition-all duration-200 hover:bg-accent hover:text-foreground ${
                  rail ? "justify-center px-0" : "px-3"
                }`}
              >
                <Settings2 className="h-[18px] w-[18px] shrink-0" />
                {!rail && <span className="min-w-0 flex-1 truncate text-left">Настройки</span>}
              </button>
            )}

            {sidebar && !rail && <div className="mt-3 pt-3">{sidebar}</div>}
          </nav>
        </div>

        {/* Подпункты уезжают ВПРАВО, а не вниз: список из пяти пунктов внутри
            меню сдвигал всё остальное и прятал избранное под сгиб. Панель
            перекрывает содержимое и закрывается кликом мимо. */}
        {openNode?.children && (
          <div
            /* Панель по высоте содержимого: во весь экран она оставляла
               огромное пустое поле под пятью пунктами */
            className="glass-strong fixed z-10 flex w-[236px] flex-col overflow-hidden rounded-2xl shadow-pop"
            style={{
              left: (rail ? 68 : 248) + 8,
              top: flyoutTop,
              animation: "slideRight 0.22s cubic-bezier(0.22,1,0.36,1) both",
            }}
          >
            <div className="flex h-11 shrink-0 items-center gap-2 px-3">
              <openNode.icon className="h-4 w-4 shrink-0 text-brand-ink" />
              <span className="min-w-0 flex-1 truncate text-[13px] font-semibold tracking-tight">
                {openNode.label}
              </span>
              <button
                type="button"
                onClick={() => setFlyout(null)}
                className="inline-flex h-7 w-7 items-center justify-center rounded-lg text-muted-foreground transition-colors hover:bg-accent"
              >
                <X className="h-3.5 w-3.5" />
              </button>
            </div>
            <div className="space-y-0.5 px-2 pb-2">
              {openNode.children.map((leaf, i) => (
                <button
                  key={leaf.key}
                  type="button"
                  onClick={() => pick(leaf.key)}
                  aria-current={leaf.key === view ? "page" : undefined}
                  style={{ animationDelay: `${i * 30}ms` }}
                  className={`rise flex h-10 w-full items-center gap-2.5 rounded-xl px-3 text-[13px] transition-all duration-200 ${
                    leaf.key === view
                      ? "bg-brand font-medium text-white shadow-sm"
                      : "text-muted-foreground hover:bg-accent hover:text-foreground"
                  }`}
                >
                  <leaf.icon className="h-4 w-4 shrink-0" />
                  <span className="min-w-0 flex-1 truncate text-left">{leaf.label}</span>
                  {leaf.badge != null && leaf.badge > 0 && (
                    <span
                      className={`shrink-0 rounded-full px-1.5 py-0.5 text-[10px] font-medium tabular-nums ${
                        leaf.key === view
                          ? "bg-white/25 text-white"
                          : "bg-foreground/10 text-muted-foreground"
                      }`}
                    >
                      {leaf.badge > 99 ? "99+" : leaf.badge}
                    </span>
                  )}
                </button>
              ))}
            </div>
          </div>
        )}
      </aside>

      {/* ------------------------------------------------------- контент */}
      <div
        className={`flex h-dvh flex-col transition-[padding] duration-300 ${
          rail ? "lg:pl-[68px]" : "lg:pl-[248px]"
        }`}
      >
        {/* Шапка уплотняется при прокрутке: пока страница вверху — она
            прозрачная и градиент виден целиком; как только контент уезжает
            под неё, появляется фон, иначе текст наезжает на текст. */}
        <header
          className={`z-20 shrink-0 border-b transition-all duration-300 ${
            scrolled
              ? "bg-background/70 shadow-card backdrop-blur-2xl"
              : "border-transparent bg-transparent"
          }`}
          style={scrolled ? { borderColor: "var(--glass-edge)" } : undefined}
        >
          <div className="flex h-14 items-center gap-2 px-3 sm:px-5">
            {/* на телефоне сайдбара нет — там вход в настройки остаётся
                кнопкой в шапке */}
            {settings && (
              <button
                type="button"
                onClick={() => setPrefs(true)}
                title="Настройки"
                aria-label="Настройки"
                className="inline-flex h-9 w-9 shrink-0 items-center justify-center rounded-xl text-muted-foreground transition-all duration-200 hover:bg-accent hover:text-foreground active:scale-95 lg:hidden"
              >
                <Menu className="h-[18px] w-[18px]" />
              </button>
            )}
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
            <div className="no-scrollbar ml-auto flex min-w-0 flex-1 items-center gap-1 overflow-x-auto pl-1 sm:justify-end sm:gap-2">
              {headerRight}
            </div>
          </div>
        </header>


        <main
          onScroll={(e) => setScrolled(e.currentTarget.scrollTop > 4)}
          className="scrollbar-thin min-h-0 w-full flex-1 overflow-y-auto px-3 pb-[4.75rem] pt-2 sm:px-5 lg:pb-4"
        >
          <div key={view} className="rise h-full min-h-0">
            {children}
          </div>
        </main>
      </div>

      {banner}

      {/* ------------------------------------------------- плавающая кнопка */}
      {fab && (
        <div className="pb-safe fixed bottom-[4.75rem] right-4 z-30 lg:bottom-6 lg:right-6">
          {fab}
        </div>
      )}

      {/* ------------------------------------------- нижняя панель (телефон) */}
      <nav
        className="pb-safe fixed inset-x-0 bottom-0 z-30 border-t bg-background/80 backdrop-blur-2xl lg:hidden"
        style={{ borderColor: "var(--glass-edge)" }}
      >
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
            className={`flex flex-1 flex-col items-center gap-1 py-2 text-[10px] transition-all duration-200 active:scale-95 ${
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
          <DialogPrimitive.Overlay className="fixed inset-0 z-40 bg-foreground/15 backdrop-blur-sm data-open:animate-in data-open:fade-in-0 data-closed:animate-out data-closed:fade-out-0 lg:hidden" />
          <DialogPrimitive.Content className="glass-strong pb-safe fixed inset-x-0 bottom-0 z-50 max-h-[88dvh] overflow-y-auto rounded-t-3xl p-4 shadow-pop data-open:animate-in data-open:slide-in-from-bottom data-closed:animate-out data-closed:slide-out-to-bottom lg:hidden">
            <div className="mx-auto mb-3 h-1 w-10 rounded-full bg-foreground/15" />
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
                        className={`flex items-center gap-2.5 rounded-2xl px-3 py-3 text-left text-sm transition-all duration-200 active:scale-[0.98] ${
                          leaf.key === view
                            ? "bg-brand font-medium text-white"
                            : "glass text-foreground"
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

            {sidebar && <div className="mt-4 pt-4">{sidebar}</div>}
          </DialogPrimitive.Content>
        </DialogPrimitive.Portal>
      </DialogPrimitive.Root>

      {/* ------------------------------------------ настройки: панель слева */}
      <DialogPrimitive.Root open={prefs} onOpenChange={setPrefs}>
        <DialogPrimitive.Portal>
          <DialogPrimitive.Overlay className="fixed inset-0 z-40 bg-foreground/15 backdrop-blur-sm data-open:animate-in data-open:fade-in-0 data-closed:animate-out data-closed:fade-out-0" />
          <DialogPrimitive.Content className="glass-strong fixed inset-y-0 left-0 z-50 flex w-full flex-col shadow-pop data-open:animate-in data-open:slide-in-from-left data-closed:animate-out data-closed:slide-out-to-left sm:w-[430px]">
            <div className="flex h-14 shrink-0 items-center gap-2 px-4">
              <DialogPrimitive.Close className="inline-flex h-9 w-9 items-center justify-center rounded-xl text-muted-foreground transition-all hover:bg-accent hover:text-foreground active:scale-95">
                <ChevronLeft className="h-5 w-5" />
              </DialogPrimitive.Close>
              <DialogPrimitive.Title className="flex-1 text-center text-[15px] font-semibold tracking-tight">
                Настройки
              </DialogPrimitive.Title>
              <ThemeToggle />
            </div>
            <DialogPrimitive.Description className="sr-only">
              Подключения, стратегия, уведомления, аккаунт и оформление
            </DialogPrimitive.Description>

            <div className="scrollbar-thin min-h-0 flex-1 space-y-4 overflow-y-auto px-4 pb-4">
              {settings}
            </div>

            <div className="shrink-0 px-4 pb-[max(1rem,env(safe-area-inset-bottom))]">
              <button
                type="button"
                onClick={onLogout}
                className="glass inline-flex h-11 w-full items-center justify-center gap-2 rounded-2xl text-sm text-neg transition-all hover:shadow-pop active:scale-[0.99]"
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
  highlighted,
  rail,
  hasChildren,
  onClick,
}: {
  item: NavLeaf;
  active: boolean;
  highlighted?: boolean;
  rail: boolean;
  hasChildren?: boolean;
  onClick: (e: React.MouseEvent<HTMLButtonElement>) => void;
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      title={rail ? item.label : undefined}
      aria-current={active ? "page" : undefined}
      aria-expanded={hasChildren ? highlighted : undefined}
      className={`group relative flex h-10 w-full items-center gap-3 rounded-xl text-sm transition-all duration-200 ${
        rail ? "justify-center px-0" : "px-3"
      } ${
        active
          ? "bg-brand font-medium text-white shadow-sm"
          : highlighted
            ? "bg-accent font-medium text-foreground"
            : "text-muted-foreground hover:bg-accent hover:text-foreground"
      }`}
    >
      <item.icon className="h-[18px] w-[18px] shrink-0" />
      {!rail && (
        <>
          <span className="min-w-0 flex-1 truncate text-left">{item.label}</span>
          {hasChildren && (
            <ChevronRight
              className={`h-3.5 w-3.5 shrink-0 transition-transform duration-200 ${
                highlighted ? "translate-x-0.5" : ""
              }`}
            />
          )}
        </>
      )}
      {item.badge != null && item.badge > 0 && (
        <span
          className={`shrink-0 rounded-full text-[10px] font-medium tabular-nums ${
            rail
              ? "absolute right-2 top-1.5 h-4 min-w-4 px-1 leading-4"
              : "px-1.5 py-0.5"
          } ${active ? "bg-white/25 text-white" : "bg-foreground/10 text-muted-foreground"}`}
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
      className={`relative flex flex-1 flex-col items-center gap-1 py-2 text-[10px] transition-all duration-200 active:scale-95 ${
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
