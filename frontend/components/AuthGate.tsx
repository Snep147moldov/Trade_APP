"use client";

import { useCallback, useEffect, useState } from "react";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { api, clearToken, getToken, setToken, type AuthUser } from "@/lib/api";

export function AuthGate({
  children,
}: {
  children: (user: AuthUser, logout: () => void) => React.ReactNode;
}) {
  const [user, setUser] = useState<AuthUser | null>(null);
  const [checking, setChecking] = useState(true);
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [totp, setTotp] = useState("");
  const [needsTotp, setNeedsTotp] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    const onUnauthorized = () => setUser(null);
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
    setPassword("");
    setTotp("");
    setNeedsTotp(false);
  }, []);

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
      setError(msg.includes("двухфакторной") ? "Неверный код 2FA" : "Неверный логин или пароль");
    }
    setBusy(false);
  };

  if (checking) {
    return (
      <div className="flex min-h-screen items-center justify-center bg-[#f5f5f7] text-sm text-muted-foreground">
        Загрузка…
      </div>
    );
  }

  if (!user) {
    return (
      <div className="flex min-h-screen items-center justify-center bg-[#f5f5f7] px-4">
        <Card className="w-full max-w-sm rounded-2xl border-black/5 shadow-sm">
          <CardContent className="pt-8 pb-6">
            <div className="mb-6 flex flex-col items-center gap-2">
              <div className="h-3 w-3 rounded-full bg-[#0a84ff]" />
              <h1 className="text-xl font-semibold tracking-tight">Codnixy AI Trade</h1>
              <p className="text-xs text-muted-foreground">Войдите, чтобы продолжить</p>
            </div>
            <form onSubmit={submit} className="space-y-3">
              <div className="space-y-1">
                <Label htmlFor="login" className="text-xs">Логин</Label>
                <Input
                  id="login"
                  className="rounded-xl"
                  autoComplete="username"
                  value={username}
                  onChange={(e) => setUsername(e.target.value)}
                />
              </div>
              <div className="space-y-1">
                <Label htmlFor="pwd" className="text-xs">Пароль</Label>
                <Input
                  id="pwd"
                  type="password"
                  className="rounded-xl"
                  autoComplete="current-password"
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                />
              </div>
              {needsTotp && (
                <div className="space-y-1">
                  <Label htmlFor="totp" className="text-xs">Код из приложения-аутентификатора</Label>
                  <Input
                    id="totp"
                    inputMode="numeric"
                    placeholder="000000"
                    className="rounded-xl text-center tracking-[0.3em]"
                    value={totp}
                    onChange={(e) => setTotp(e.target.value)}
                  />
                </div>
              )}
              {error && <p className="text-center text-xs text-[#ff3b30]">{error}</p>}
              <Button type="submit" className="w-full rounded-xl" disabled={busy}>
                {busy ? "Вхожу…" : "Войти"}
              </Button>
            </form>
            <p className="mt-4 text-center text-[10px] text-muted-foreground">
              Первый вход: admin / admin12345 — смените пароль в настройках аккаунта.
            </p>
          </CardContent>
        </Card>
      </div>
    );
  }

  return <>{children(user, logout)}</>;
}
