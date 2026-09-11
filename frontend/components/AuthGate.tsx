"use client";

import { useCallback, useEffect, useState } from "react";
import { ArrowLeft, LoaderCircle } from "lucide-react";

import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { PasswordInput } from "@/components/ui/password-input";
import { api, clearToken, getToken, setToken, type AuthUser } from "@/lib/api";

type Mode = "login" | "forgot" | "code";

/** Экран входа и всё, что вокруг него: вход, 2FA, восстановление доступа и
 *  ожидание, пока приложение подтянет данные. */
export function AuthGate({
  children,
}: {
  children: (
    user: AuthUser,
    logout: () => void,
    onReady: () => void,
  ) => React.ReactNode;
}) {
  const [user, setUser] = useState<AuthUser | null>(null);
  const [checking, setChecking] = useState(true);
  // приложение смонтировано, но данные ещё грузятся: держим экран входа с
  // кружком, иначе пользователь попадает в пустой интерфейс и смотрит, как он
  // наполняется по кускам
  const [appReady, setAppReady] = useState(false);

  const [mode, setMode] = useState<Mode>("login");
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [totp, setTotp] = useState("");
  const [needsTotp, setNeedsTotp] = useState(false);
  const [code, setCode] = useState("");
  const [newPwd, setNewPwd] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  // счётчик перезапускает анимацию тряски при каждой новой ошибке: без смены
  // ключа CSS-анимация второй раз не проигрывается
  const [shake, setShake] = useState(0);

  const fail = (msg: string) => {
    setError(msg);
    setShake((n) => n + 1);
  };

  useEffect(() => {
    const onUnauthorized = () => {
      setUser(null);
      setAppReady(false);
    };
    window.addEventListener("cnx-unauthorized", onUnauthorized);
    if (getToken()) {
      api.me().then(setUser).catch(() => clearToken()).finally(() => setChecking(false));
    } else {
      setChecking(false);
    }
    return () => window.removeEventListener("cnx-unauthorized", onUnauthorized);
  }, []);

  const logout = useCallback(() => {
    api.logout().catch(() => {});
    clearToken();
    setUser(null);
    setAppReady(false);
    setPassword("");
    setTotp("");
    setNeedsTotp(false);
    setMode("login");
  }, []);

  const onReady = useCallback(() => setAppReady(true), []);

  const submit = async (e: React.FormEvent) => {
    e.preventDefault();
    setBusy(true);
    setError(null);
    try {
      const r = await api.login(username, password, totp || undefined);
      if (r.requires_totp) {
        setNeedsTotp(true);
      } else if (r.token && r.user) {
        setToken(r.token);
        setUser(r.user);
      }
    } catch (err) {
      const msg = err instanceof Error ? err.message : "";
      fail(msg.includes("двухфакторной") ? "Неверный код 2FA" : "Неверный логин или пароль");
    }
    setBusy(false);
  };

  const requestCode = async (e: React.FormEvent) => {
    e.preventDefault();
    setBusy(true);
    setError(null);
    try {
      const r = await api.forgotPassword(username);
      setNotice(r.detail);
      setMode("code");
    } catch {
      fail("Не удалось отправить код");
    }
    setBusy(false);
  };

  const applyReset = async (e: React.FormEvent) => {
    e.preventDefault();
    setBusy(true);
    setError(null);
    try {
      const r = await api.resetPassword(username, code, newPwd);
      setNotice(r.detail);
      setMode("login");
      setCode("");
      setNewPwd("");
      setPassword("");
    } catch (err) {
      fail(err instanceof Error ? err.message : "Код неверный или истёк");
    }
    setBusy(false);
  };

  // ------------------------------------------------------- экран ожидания
  if (checking) {
    return <Splash caption="Проверяю сессию…" />;
  }

  if (user) {
    return (
      <>
        {/* приложение уже монтируется и грузит данные, но скрыто, пока не
            сообщит о готовности */}
        <div className={appReady ? undefined : "pointer-events-none invisible"}>
          {children(user, logout, onReady)}
        </div>
        {!appReady && <Splash caption="Загружаю данные…" />}
      </>
    );
  }

  const bad = Boolean(error);

  return (
    <Shell>
      <Card
        key={shake}
        className={`relative z-10 w-full max-w-sm rounded-3xl shadow-pop ${bad ? "shake" : ""}`}
      >
        <CardContent className="pb-6 pt-8">
          <div className="mb-6 flex flex-col items-center gap-2.5">
            <span className="logo-mark rise h-16 w-16 text-brand" aria-hidden />
            <h1 className="text-2xl font-semibold tracking-tight">Aurex</h1>
            <p className="text-xs text-muted-foreground">
              {mode === "login"
                ? "Войдите, чтобы продолжить"
                : mode === "forgot"
                  ? "Восстановление доступа"
                  : "Введите код из письма"}
            </p>
          </div>

          {mode === "login" && (
            <form onSubmit={submit} className="space-y-3">
              <Field label="Логин" htmlFor="login">
                <Input
                  id="login"
                  className={`rounded-xl ${bad ? "border-neg ring-1 ring-neg/40" : ""}`}
                  autoComplete="username"
                  value={username}
                  onChange={(e) => setUsername(e.target.value)}
                />
              </Field>
              <Field label="Пароль" htmlFor="pwd">
                <PasswordInput
                  id="pwd"
                  className={`rounded-xl ${bad ? "border-neg ring-1 ring-neg/40" : ""}`}
                  autoComplete="current-password"
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                />
              </Field>
              {needsTotp && (
                <Field label="Код из приложения-аутентификатора" htmlFor="totp">
                  <Input
                    id="totp"
                    inputMode="numeric"
                    className={`rounded-xl tracking-[0.3em] ${bad ? "border-neg ring-1 ring-neg/40" : ""}`}
                    value={totp}
                    onChange={(e) => setTotp(e.target.value)}
                  />
                </Field>
              )}
              <Submit busy={busy} label="Войти" />
              <button
                type="button"
                onClick={() => {
                  setMode("forgot");
                  setError(null);
                  setNotice(null);
                }}
                className="w-full text-center text-xs text-brand-ink transition-colors hover:underline"
              >
                Забыли пароль?
              </button>
            </form>
          )}

          {mode === "forgot" && (
            <form onSubmit={requestCode} className="space-y-3">
              <Field label="Логин" htmlFor="fuser">
                <Input
                  id="fuser"
                  className={`rounded-xl ${bad ? "border-neg ring-1 ring-neg/40" : ""}`}
                  value={username}
                  onChange={(e) => setUsername(e.target.value)}
                />
              </Field>
              <p className="text-[11px] leading-relaxed text-muted-foreground">
                Код уйдёт на адрес, привязанный к учётной записи. Если адреса нет,
                пароль меняет администратор в разделе «Пользователи».
              </p>
              <Submit busy={busy} label="Выслать код" />
              <Back onClick={() => setMode("login")} />
            </form>
          )}

          {mode === "code" && (
            <form onSubmit={applyReset} className="space-y-3">
              <Field label="Код из письма" htmlFor="rcode">
                <Input
                  id="rcode"
                  inputMode="numeric"
                  className={`rounded-xl tracking-[0.3em] ${bad ? "border-neg ring-1 ring-neg/40" : ""}`}
                  value={code}
                  onChange={(e) => setCode(e.target.value)}
                />
              </Field>
              <Field label="Новый пароль (мин. 8 символов)" htmlFor="rpwd">
                <PasswordInput
                  id="rpwd"
                  className={`rounded-xl ${bad ? "border-neg ring-1 ring-neg/40" : ""}`}
                  autoComplete="new-password"
                  value={newPwd}
                  onChange={(e) => setNewPwd(e.target.value)}
                />
              </Field>
              <Submit busy={busy} label="Сменить пароль" disabled={newPwd.length < 8} />
              <Back onClick={() => setMode("login")} />
            </form>
          )}

          {error && (
            <p className="mt-3 text-center text-xs font-medium text-neg">{error}</p>
          )}
          {!error && notice && (
            <p className="mt-3 text-center text-xs text-muted-foreground">{notice}</p>
          )}
        </CardContent>
      </Card>
    </Shell>
  );
}

/** Фон с водяным знаком — общий для входа и экрана загрузки, чтобы переход
 *  между ними не выглядел сменой страницы. */
function Shell({
  children,
  overlay,
}: {
  children: React.ReactNode;
  /** поверх приложения, а не под ним: скрытое приложение сохраняет высоту,
      и обычный блок уезжал за нижнюю границу экрана */
  overlay?: boolean;
}) {
  return (
    <div
      className={`flex items-center justify-center overflow-hidden px-4 ${
        overlay
          // без своего фона: приложение под ним скрыто и ничего не рисует,
          // зато сквозь оверлей виден градиент страницы
          ? "fixed inset-0 z-50"
          : "relative min-h-dvh"
      }`}
    >
      <span
        aria-hidden
        className="logo-mark pointer-events-none absolute -right-[10%] top-1/4 h-[102dvh] w-[102dvh] -rotate-[20deg] text-brand opacity-[0.16]"
        style={{
          filter: "drop-shadow(0 0 5px currentColor) drop-shadow(0 0 2px currentColor)",
        }}
      />
      {children}
    </div>
  );
}

function Splash({ caption }: { caption: string }) {
  return (
    <Shell overlay>
      <div className="relative z-10 flex flex-col items-center gap-4">
        <span className="relative flex h-20 w-20 items-center justify-center">
          <LoaderCircle className="absolute h-20 w-20 animate-spin text-brand/35" strokeWidth={1.5} />
          <span className="logo-mark h-10 w-10 text-brand" aria-hidden />
        </span>
        <p className="text-sm font-medium tracking-tight">Aurex</p>
        <p className="-mt-2 text-xs text-muted-foreground">{caption}</p>
      </div>
    </Shell>
  );
}

function Field({
  label,
  htmlFor,
  children,
}: {
  label: string;
  htmlFor: string;
  children: React.ReactNode;
}) {
  return (
    <div className="space-y-1">
      <Label htmlFor={htmlFor} className="text-xs">
        {label}
      </Label>
      {children}
    </div>
  );
}

function Submit({
  busy,
  label,
  disabled,
}: {
  busy: boolean;
  label: string;
  disabled?: boolean;
}) {
  return (
    <Button type="submit" className="w-full rounded-xl" disabled={busy || disabled}>
      {busy ? <LoaderCircle className="h-4 w-4 animate-spin" /> : label}
    </Button>
  );
}

function Back({ onClick }: { onClick: () => void }) {
  return (
    <button
      type="button"
      onClick={onClick}
      className="flex w-full items-center justify-center gap-1 text-xs text-muted-foreground transition-colors hover:text-foreground"
    >
      <ArrowLeft className="h-3 w-3" /> Назад ко входу
    </button>
  );
}
