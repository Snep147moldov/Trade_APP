"use client";

import { useCallback, useEffect, useState } from "react";
import {
  Activity,
  BarChart3,
  CreditCard,
  LayoutDashboard,
  Search,
  Users,
} from "lucide-react";

import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import {
  api,
  type AdminCharts,
  type AdminOverview,
  type AdminSubscriptionRow,
  type AdminUserDetail,
  type PaymentRow,
  type UserEventRow,
} from "@/lib/api";
import { tr } from "@/lib/i18n";

type Tab = "overview" | "users" | "billing" | "activity" | "charts";

const TABS: { key: Tab; label: string; icon: typeof Users }[] = [
  { key: "overview", label: "Обзор", icon: LayoutDashboard },
  { key: "users", label: "Пользователи", icon: Users },
  { key: "billing", label: "Оплаты", icon: CreditCard },
  { key: "activity", label: "Активность", icon: Activity },
  { key: "charts", label: "Графики", icon: BarChart3 },
];

/** Подписи состояний подписки. */
const STATUS_LABEL: Record<string, string> = {
  trialing: "Пробный",
  active: "Активна",
  past_due: "Просрочена",
  suspended: "Приостановлена",
  cancelled: "Отменена",
  expired: "Истекла",
};

const money = (cents: number, currency = "EUR") =>
  `${(cents / 100).toLocaleString(undefined, { minimumFractionDigits: 2 })} ${currency}`;

/**
 * Панель администратора: обзор, люди, деньги, активность, графики.
 *
 * Все действия ходят через `/api/admin/*`, и каждый такой маршрут проверяет
 * роль на сервере. Эта панель — удобство, а не защита: спрятанная кнопка
 * ничего не закрывает.
 *
 * Ни один ответ сервера не содержит пароля брокера или ключа API — только
 * признак, что они заданы. Поэтому здесь нечего случайно показать.
 */
export function AdminPanel({ trigger }: { trigger: React.ReactNode }) {
  const [open, setOpen] = useState(false);
  const [tab, setTab] = useState<Tab>("overview");

  return (
    <Dialog open={open} onOpenChange={setOpen}>
      <DialogTrigger asChild>{trigger}</DialogTrigger>
      <DialogContent className="max-h-[92dvh] overflow-hidden p-0 sm:max-w-5xl">
        <DialogHeader className="px-5 pt-5">
          <DialogTitle className="tracking-tight">{tr("Управление")}</DialogTitle>
        </DialogHeader>

        <div className="flex gap-1 overflow-x-auto px-5 pb-2">
          {TABS.map((t) => (
            <button
              key={t.key}
              type="button"
              onClick={() => setTab(t.key)}
              className={`flex shrink-0 items-center gap-1.5 rounded-xl px-3 py-1.5 text-[13px] transition-colors sm:text-xs ${
                tab === t.key
                  ? "bg-brand font-medium text-white"
                  : "text-muted-foreground hover:bg-accent hover:text-foreground"
              }`}
            >
              <t.icon className="h-3.5 w-3.5" />
              {tr(t.label)}
            </button>
          ))}
        </div>

        <div className="max-h-[72dvh] overflow-y-auto px-5 pb-5">
          {open && tab === "overview" && <OverviewTab />}
          {open && tab === "users" && <UsersTab />}
          {open && tab === "billing" && <BillingTab />}
          {open && tab === "activity" && <ActivityTab />}
          {open && tab === "charts" && <ChartsTab />}
        </div>
      </DialogContent>
    </Dialog>
  );
}

// --------------------------------------------------------------------------
// Обзор
// --------------------------------------------------------------------------

function OverviewTab() {
  const [data, setData] = useState<AdminOverview | null>(null);
  useEffect(() => {
    api.adminOverview().then(setData).catch(() => setData(null));
  }, []);

  if (!data) return <Loading />;

  return (
    <div className="space-y-4">
      <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
        <Stat label={tr("Пользователей")} value={String(data.users_total)} hint={tr("+{0} за сутки", data.users_new_24h)} />
        <Stat label={tr("Доход за месяц")} value={money(data.revenue_month_cents)} />
        <Stat label={tr("MRR")} value={money(data.mrr_cents)} hint={tr("по активным подпискам")} />
        <Stat
          label={tr("Истекает за 7 дней")}
          value={String(data.due_in_7_days)}
          tone={data.due_in_7_days > 0 ? "warn" : undefined}
        />
        <Stat label={tr("Открытых сигналов")} value={String(data.signals_open)} />
        <Stat label={tr("Сигналов за сутки")} value={String(data.signals_24h)} />
        <Stat label={tr("Действий за сутки")} value={String(data.events_24h)} />
        <Stat
          label={tr("Приостановлено")}
          value={String(data.subscriptions_by_status.suspended ?? 0)}
          tone={(data.subscriptions_by_status.suspended ?? 0) > 0 ? "neg" : undefined}
        />
      </div>

      <section>
        <h3 className="mb-2 text-[13px] font-medium uppercase tracking-wide text-muted-foreground">
          {tr("Подписки по состоянию")}
        </h3>
        <div className="glass space-y-1.5 rounded-2xl p-3 text-sm sm:text-[13px]">
          {Object.entries(data.subscriptions_by_status).map(([status, count]) => (
            <div key={status} className="flex justify-between">
              <span className="text-muted-foreground">{tr(STATUS_LABEL[status] ?? status)}</span>
              <span className="tabular-nums">{count}</span>
            </div>
          ))}
        </div>
      </section>

      <section>
        <h3 className="mb-2 text-[13px] font-medium uppercase tracking-wide text-muted-foreground">
          {tr("Подписки по тарифу")}
        </h3>
        <div className="glass space-y-1.5 rounded-2xl p-3 text-sm sm:text-[13px]">
          {Object.entries(data.subscriptions_by_plan).map(([plan, count]) => (
            <div key={plan} className="flex justify-between">
              <span className="text-muted-foreground">{plan}</span>
              <span className="tabular-nums">{count}</span>
            </div>
          ))}
        </div>
      </section>
    </div>
  );
}

// --------------------------------------------------------------------------
// Пользователи
// --------------------------------------------------------------------------

function UsersTab() {
  const [rows, setRows] = useState<AdminSubscriptionRow[]>([]);
  const [query, setQuery] = useState("");
  const [selected, setSelected] = useState<number | null>(null);

  const reload = useCallback(() => {
    api.adminSubscriptions("all").then(setRows).catch(() => setRows([]));
  }, []);
  useEffect(reload, [reload]);

  const filtered = rows.filter(
    (r) =>
      !query ||
      r.username.toLowerCase().includes(query.toLowerCase()) ||
      r.email.toLowerCase().includes(query.toLowerCase()),
  );

  if (selected !== null) {
    return <UserDetail userId={selected} onBack={() => { setSelected(null); reload(); }} />;
  }

  return (
    <div className="space-y-3">
      <div className="relative">
        <Search className="absolute left-3 top-1/2 h-3.5 w-3.5 -translate-y-1/2 text-muted-foreground" />
        <Input
          className="rounded-xl pl-9"
          placeholder={tr("Поиск по логину или почте")}
          value={query}
          onChange={(e) => setQuery(e.target.value)}
        />
      </div>

      <div className="glass divide-y rounded-2xl text-sm sm:text-[13px]">
        {filtered.length === 0 && (
          <p className="px-3 py-4 text-center text-xs text-muted-foreground">
            {tr("Никого не найдено.")}
          </p>
        )}
        {filtered.map((r) => (
          <button
            key={r.user_id}
            type="button"
            onClick={() => setSelected(r.user_id)}
            className="flex w-full items-center gap-3 px-3 py-2.5 text-left transition-colors hover:bg-accent"
          >
            <span className="min-w-0 flex-1">
              <span className="block truncate font-medium">{r.username}</span>
              <span className="block truncate text-xs text-muted-foreground">
                {r.email || tr("без почты")} · {r.plan_name}
              </span>
            </span>
            <StatusChip status={r.status} />
            <span className="w-16 shrink-0 text-right text-xs tabular-nums text-muted-foreground">
              {r.days_left === null ? "—" : tr("{0} дн.", r.days_left)}
            </span>
          </button>
        ))}
      </div>
    </div>
  );
}

function UserDetail({ userId, onBack }: { userId: number; onBack: () => void }) {
  const [data, setData] = useState<AdminUserDetail | null>(null);
  const [busy, setBusy] = useState(false);
  const [note, setNote] = useState<string | null>(null);

  const load = useCallback(() => {
    api.adminUserDetail(userId).then(setData).catch(() => setData(null));
  }, [userId]);
  useEffect(load, [load]);

  const act = async (fn: () => Promise<unknown>, done: string) => {
    setBusy(true);
    try {
      await fn();
      setNote(done);
      load();
    } catch (err) {
      setNote(err instanceof Error ? err.message : String(err));
    }
    setBusy(false);
  };

  if (!data) return <Loading />;
  const sub = data.subscription;

  return (
    <div className="space-y-4">
      <button type="button" onClick={onBack} className="text-xs text-brand-ink hover:underline">
        ← {tr("Ко всем пользователям")}
      </button>

      <div className="glass rounded-2xl p-4">
        <div className="flex flex-wrap items-baseline justify-between gap-2">
          <div>
            <p className="text-lg font-semibold tracking-tight">{data.user.username}</p>
            <p className="text-xs text-muted-foreground">
              {data.user.email || tr("без почты")} · {data.user.role} · {data.user.language}
            </p>
          </div>
          {sub && <StatusChip status={sub.status} />}
        </div>

        <dl className="mt-4 grid grid-cols-2 gap-3 text-sm sm:text-[13px]">
          <Field label={tr("Тариф")} value={sub?.plan_name ?? tr("нет")} />
          <Field
            label={tr("Оплачено до")}
            value={sub?.current_period_end ? new Date(sub.current_period_end).toLocaleDateString() : "—"}
          />
          <Field
            label={tr("Осталось")}
            value={sub?.days_left == null ? "—" : tr("{0} дн.", sub.days_left)}
          />
          <Field label={tr("Активных сессий")} value={String(data.user.active_sessions)} />
          <Field label={tr("2FA")} value={data.user.totp_enabled ? tr("включена") : tr("выключена")} />
          <Field
            label={tr("Зарегистрирован")}
            value={data.user.created_at ? new Date(data.user.created_at).toLocaleDateString() : "—"}
          />
        </dl>
      </div>

      <section className="space-y-2">
        <h3 className="text-[13px] font-medium uppercase tracking-wide text-muted-foreground">
          {tr("Подписка")}
        </h3>
        <div className="flex flex-wrap gap-2">
          {[7, 30, 90, 365].map((days) => (
            <Button
              key={days}
              size="sm"
              variant="outline"
              disabled={busy}
              className="rounded-lg text-xs"
              onClick={() => act(() => api.adminExtend(userId, days), tr("Продлено на {0} дн.", days))}
            >
              +{days} {tr("дн.")}
            </Button>
          ))}
          <Button
            size="sm"
            variant="outline"
            disabled={busy}
            className="rounded-lg text-xs text-neg"
            onClick={() => act(() => api.adminSetSubscriptionStatus(userId, "suspended"), tr("Приостановлено"))}
          >
            {tr("Приостановить")}
          </Button>
          <Button
            size="sm"
            variant="outline"
            disabled={busy}
            className="rounded-lg text-xs"
            onClick={() => act(() => api.adminSetSubscriptionStatus(userId, "active"), tr("Возобновлено"))}
          >
            {tr("Возобновить")}
          </Button>
        </div>
        <PlanPicker userId={userId} busy={busy} onDone={(m) => { setNote(m); load(); }} />
      </section>

      <section className="space-y-2">
        <h3 className="text-[13px] font-medium uppercase tracking-wide text-muted-foreground">
          {tr("Аккаунт")}
        </h3>
        <div className="flex flex-wrap gap-2">
          <Button
            size="sm"
            variant="outline"
            disabled={busy}
            className="rounded-lg text-xs"
            onClick={() => act(() => api.adminLogoutAll(userId), tr("Сессии завершены"))}
          >
            {tr("Выйти на всех устройствах")}
          </Button>
          <PasswordReset userId={userId} onDone={(m) => setNote(m)} />
        </div>
      </section>

      {note && <p className="text-xs text-brand-ink">{note}</p>}

      <section>
        <h3 className="mb-2 text-[13px] font-medium uppercase tracking-wide text-muted-foreground">
          {tr("Оплаты")}
        </h3>
        <PaymentList rows={data.payments} />
      </section>

      <section>
        <h3 className="mb-2 text-[13px] font-medium uppercase tracking-wide text-muted-foreground">
          {tr("Активность")}
        </h3>
        <EventList rows={data.events} />
      </section>
    </div>
  );
}

function PlanPicker({
  userId,
  busy,
  onDone,
}: {
  userId: number;
  busy: boolean;
  onDone: (note: string) => void;
}) {
  const [plans, setPlans] = useState<{ code: string; name: string }[]>([]);
  useEffect(() => {
    api.plans().then((p) => setPlans(p.map((x) => ({ code: x.code, name: x.name })))).catch(() => {});
  }, []);

  return (
    <div className="flex flex-wrap items-center gap-2">
      <span className="text-xs text-muted-foreground">{tr("Сменить тариф:")}</span>
      {plans.map((p) => (
        <Button
          key={p.code}
          size="sm"
          variant="outline"
          disabled={busy}
          className="rounded-lg text-xs"
          onClick={() =>
            api
              .adminSetPlan(userId, { plan_code: p.code })
              .then(() => onDone(tr("Тариф изменён на {0}", p.name)))
              .catch((e) => onDone(e instanceof Error ? e.message : String(e)))
          }
        >
          {p.name}
        </Button>
      ))}
    </div>
  );
}

function PasswordReset({ userId, onDone }: { userId: number; onDone: (note: string) => void }) {
  const [value, setValue] = useState("");
  return (
    <span className="flex items-center gap-1.5">
      <Input
        className="h-8 w-40 rounded-lg text-xs"
        type="password"
        placeholder={tr("новый пароль")}
        value={value}
        onChange={(e) => setValue(e.target.value)}
      />
      <Button
        size="sm"
        variant="outline"
        className="rounded-lg text-xs"
        disabled={value.length < 8}
        onClick={() =>
          api
            .adminSetPassword(userId, value)
            .then(() => {
              setValue("");
              onDone(tr("Пароль изменён, сессии завершены"));
            })
            .catch((e) => onDone(e instanceof Error ? e.message : String(e)))
        }
      >
        {tr("Сменить")}
      </Button>
    </span>
  );
}

// --------------------------------------------------------------------------
// Оплаты
// --------------------------------------------------------------------------

function BillingTab() {
  const [view, setView] = useState("due_soon");
  const [rows, setRows] = useState<AdminSubscriptionRow[]>([]);
  const [payments, setPayments] = useState<PaymentRow[]>([]);

  useEffect(() => {
    api.adminSubscriptions(view).then(setRows).catch(() => setRows([]));
  }, [view]);
  useEffect(() => {
    api.adminPayments(100).then(setPayments).catch(() => setPayments([]));
  }, []);

  const views = [
    { key: "due_soon", label: "Истекают за 7 дней" },
    { key: "past_due", label: "Просрочены" },
    { key: "suspended", label: "Приостановлены" },
    { key: "trialing", label: "Пробные" },
    { key: "all", label: "Все" },
  ];

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap gap-1">
        {views.map((v) => (
          <button
            key={v.key}
            type="button"
            onClick={() => setView(v.key)}
            className={`rounded-lg px-2.5 py-1 text-xs transition-colors ${
              view === v.key ? "bg-brand font-medium text-white" : "text-muted-foreground hover:bg-accent"
            }`}
          >
            {tr(v.label)}
          </button>
        ))}
      </div>

      <div className="glass divide-y rounded-2xl text-sm sm:text-[13px]">
        {rows.length === 0 && (
          <p className="px-3 py-4 text-center text-xs text-muted-foreground">{tr("Пусто.")}</p>
        )}
        {rows.map((r) => (
          <div key={r.user_id} className="flex items-center gap-3 px-3 py-2.5">
            <span className="min-w-0 flex-1">
              <span className="block truncate font-medium">{r.username}</span>
              <span className="block truncate text-xs text-muted-foreground">
                {r.plan_name} · {money(r.price_cents)}
              </span>
            </span>
            <StatusChip status={r.status} />
            <span className="w-20 shrink-0 text-right text-xs tabular-nums text-muted-foreground">
              {r.current_period_end ? new Date(r.current_period_end).toLocaleDateString() : "—"}
            </span>
          </div>
        ))}
      </div>

      <section>
        <h3 className="mb-2 text-[13px] font-medium uppercase tracking-wide text-muted-foreground">
          {tr("Последние оплаты")}
        </h3>
        <PaymentList rows={payments} showUser />
      </section>
    </div>
  );
}

function PaymentList({ rows, showUser }: { rows: PaymentRow[]; showUser?: boolean }) {
  if (rows.length === 0) {
    return <p className="text-xs text-muted-foreground">{tr("Оплат пока не было.")}</p>;
  }
  return (
    <ul className="glass divide-y rounded-2xl text-sm sm:text-[13px]">
      {rows.map((p) => (
        <li key={p.id} className="flex items-center justify-between gap-3 px-3 py-2">
          <span className="text-xs text-muted-foreground">
            {p.created_at ? new Date(p.created_at).toLocaleDateString() : "—"}
          </span>
          {showUser && <span className="min-w-0 flex-1 truncate">{p.username}</span>}
          <span className="truncate text-xs text-muted-foreground">{p.source}</span>
          <span className="tabular-nums">{money(p.amount_cents, p.currency)}</span>
        </li>
      ))}
    </ul>
  );
}

// --------------------------------------------------------------------------
// Активность и графики
// --------------------------------------------------------------------------

function ActivityTab() {
  const [rows, setRows] = useState<UserEventRow[]>([]);
  useEffect(() => {
    api.adminEvents({ limit: 300 }).then(setRows).catch(() => setRows([]));
  }, []);
  return <EventList rows={rows} showUser />;
}

function EventList({ rows, showUser }: { rows: UserEventRow[]; showUser?: boolean }) {
  if (rows.length === 0) {
    return <p className="text-xs text-muted-foreground">{tr("Событий пока нет.")}</p>;
  }
  return (
    <ul className="glass divide-y rounded-2xl text-sm sm:text-[13px]">
      {rows.map((e) => (
        <li key={e.id} className="flex items-center gap-3 px-3 py-2">
          <span className="w-32 shrink-0 text-xs text-muted-foreground">
            {e.created_at ? new Date(e.created_at).toLocaleString() : "—"}
          </span>
          {showUser && <span className="w-28 shrink-0 truncate">{e.username}</span>}
          <span className="shrink-0 rounded bg-muted px-1.5 py-0.5 text-[11px]">{e.kind}</span>
          <span className="min-w-0 flex-1 truncate text-xs text-muted-foreground">{e.detail}</span>
          <span className="hidden shrink-0 text-[11px] text-muted-foreground sm:block">{e.ip}</span>
        </li>
      ))}
    </ul>
  );
}

function ChartsTab() {
  const [data, setData] = useState<AdminCharts | null>(null);
  useEffect(() => {
    api.adminCharts(30).then(setData).catch(() => setData(null));
  }, []);
  if (!data) return <Loading />;

  return (
    <div className="space-y-4">
      <Spark title={tr("Регистрации")} days={data.days} values={data.signups} />
      <Spark title={tr("Сигналы")} days={data.days} values={data.signals} />
      <Spark title={tr("Активность")} days={data.days} values={data.events} />
      <Spark
        title={tr("Доход, €")}
        days={data.days}
        values={data.revenue_cents.map((c) => c / 100)}
      />
    </div>
  );
}

/**
 * Столбики за период.
 *
 * Нарисованы div-ами, а не графической библиотекой: ряд из тридцати чисел не
 * стоит ещё одной зависимости в бандле, и так он одинаково выглядит в обеих
 * темах без возни с цветами на canvas.
 */
function Spark({ title, days, values }: { title: string; days: string[]; values: number[] }) {
  const max = Math.max(1, ...values);
  const total = values.reduce((a, b) => a + b, 0);
  return (
    <section>
      <div className="mb-1 flex items-baseline justify-between">
        <h3 className="text-[13px] font-medium uppercase tracking-wide text-muted-foreground">
          {title}
        </h3>
        <span className="text-xs tabular-nums text-muted-foreground">
          {tr("всего")} {total.toLocaleString()}
        </span>
      </div>
      <div className="glass flex h-24 items-end gap-[2px] rounded-2xl p-2">
        {values.map((v, i) => (
          <div
            key={days[i]}
            title={`${days[i]}: ${v}`}
            style={{ height: `${Math.max(2, (v / max) * 100)}%` }}
            className="flex-1 rounded-sm bg-brand/70"
          />
        ))}
      </div>
    </section>
  );
}

// --------------------------------------------------------------------------
// Мелочи
// --------------------------------------------------------------------------

function Stat({
  label,
  value,
  hint,
  tone,
}: {
  label: string;
  value: string;
  hint?: string;
  tone?: "warn" | "neg";
}) {
  return (
    <div className="glass rounded-2xl p-3">
      <p className="text-[11px] text-muted-foreground">{label}</p>
      <p
        className={`text-lg font-semibold tabular-nums ${
          tone === "neg" ? "text-neg" : tone === "warn" ? "text-warn" : ""
        }`}
      >
        {value}
      </p>
      {hint && <p className="text-[11px] text-muted-foreground">{hint}</p>}
    </div>
  );
}

function StatusChip({ status }: { status: string }) {
  const good = status === "active" || status === "trialing";
  const warn = status === "past_due";
  return (
    <span
      className={`shrink-0 rounded-full px-2 py-0.5 text-[11px] font-medium ${
        good ? "bg-pos/10 text-pos" : warn ? "bg-warn/10 text-warn" : "bg-neg/10 text-neg"
      }`}
    >
      {tr(STATUS_LABEL[status] ?? status)}
    </span>
  );
}

function Field({ label, value }: { label: string; value: string }) {
  return (
    <div>
      <dt className="text-xs text-muted-foreground">{label}</dt>
      <dd className="tabular-nums">{value}</dd>
    </div>
  );
}

function Loading() {
  return <p className="py-6 text-center text-sm text-muted-foreground">{tr("Загружаю")}…</p>;
}
