"use client";

import { useState } from "react";
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
import { PasswordInput } from "@/components/ui/password-input";
import { Label } from "@/components/ui/label";
import { Separator } from "@/components/ui/separator";
import { api, type AuthUser } from "@/lib/api";

export function AccountDialog({
  user,
  onUserChange,
  trigger,
}: {
  user: AuthUser;
  onUserChange: (u: AuthUser) => void;
  trigger?: React.ReactNode;
}) {
  const [open, setOpen] = useState(false);
  const [email, setEmail] = useState(user.email ?? "");
  const [curPwd, setCurPwd] = useState("");
  const [newPwd, setNewPwd] = useState("");
  const [pwdMsg, setPwdMsg] = useState<string | null>(null);
  const [totpSecret, setTotpSecret] = useState<{ secret: string; uri: string } | null>(null);
  const [totpCode, setTotpCode] = useState("");
  const [totpMsg, setTotpMsg] = useState<string | null>(null);

  const saveEmail = async () => {
    try {
      onUserChange(await api.changeEmail(email.trim()));
      setPwdMsg("Адрес сохранён.");
    } catch (e) {
      setPwdMsg(e instanceof Error ? e.message : "Не удалось сохранить адрес.");
    }
  };

  const changePwd = async () => {
    setPwdMsg(null);
    try {
      await api.changePassword(curPwd, newPwd);
      setPwdMsg("✅ Пароль изменён.");
      setCurPwd("");
      setNewPwd("");
    } catch (e) {
      setPwdMsg(`❌ ${e instanceof Error ? e.message.replace(/^\d+\s*/, "").slice(0, 120) : "ошибка"}`);
    }
  };

  const setup2fa = async () => {
    setTotpMsg(null);
    try {
      setTotpSecret(await api.totpSetup());
    } catch {
      setTotpMsg("❌ Не удалось создать секрет.");
    }
  };

  const enable2fa = async () => {
    setTotpMsg(null);
    try {
      await api.totpEnable(totpCode);
      setTotpMsg("✅ Двухфакторная аутентификация включена.");
      setTotpSecret(null);
      setTotpCode("");
      onUserChange({ ...user, totp_enabled: true });
    } catch {
      setTotpMsg("❌ Код не подошёл — проверьте приложение.");
    }
  };

  const disable2fa = async () => {
    setTotpMsg(null);
    try {
      await api.totpDisable(totpCode);
      setTotpMsg("2FA выключена.");
      setTotpCode("");
      onUserChange({ ...user, totp_enabled: false });
    } catch {
      setTotpMsg("❌ Неверный код.");
    }
  };

  return (
    <Dialog open={open} onOpenChange={setOpen}>
      <DialogTrigger asChild>
        {trigger ?? (
          <Button variant="outline" size="sm" className="rounded-xl">
            {user.username}
          </Button>
        )}
      </DialogTrigger>
      <DialogContent className="max-h-[85vh] overflow-y-auto rounded-2xl sm:max-w-[460px]">
        <DialogHeader>
          <DialogTitle className="tracking-tight">Аккаунт: {user.username}</DialogTitle>
          <DialogDescription>
            Роль: {user.role === "admin" ? "администратор" : "пользователь"}
          </DialogDescription>
        </DialogHeader>

        <p className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">
          Смена пароля
        </p>
        <div className="space-y-2">
          <div className="space-y-1">
            <Label className="text-xs">
              Почта для восстановления доступа
            </Label>
            <div className="flex gap-2">
              <Input
                className="rounded-xl"
                type="email"
                placeholder="пусто — восстановление отключено"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
              />
              <Button
                variant="outline"
                size="sm"
                className="shrink-0 rounded-xl"
                onClick={saveEmail}
                disabled={email === (user.email ?? "")}
              >
                Сохранить
              </Button>
            </div>
            <p className="text-[11px] text-muted-foreground">
              На этот адрес придёт код, если забудете пароль. Без адреса пароль
              меняет только администратор.
            </p>
          </div>
          <div className="space-y-1">
            <Label className="text-xs">Текущий пароль</Label>
            <PasswordInput className="rounded-xl" value={curPwd}
                   onChange={(e) => setCurPwd(e.target.value)} />
          </div>
          <div className="space-y-1">
            <Label className="text-xs">Новый пароль (мин. 8 символов)</Label>
            <PasswordInput className="rounded-xl" value={newPwd}
                   onChange={(e) => setNewPwd(e.target.value)} />
          </div>
          <Button variant="outline" size="sm" className="rounded-xl" onClick={changePwd}
                  disabled={!curPwd || newPwd.length < 8}>
            Сменить пароль
          </Button>
          {pwdMsg && <p className="text-xs text-muted-foreground">{pwdMsg}</p>}
        </div>

        <Separator />

        <p className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">
          Двухфакторная аутентификация (TOTP)
        </p>
        {user.totp_enabled ? (
          <div className="space-y-2">
            <p className="text-xs text-pos">2FA включена.</p>
            <div className="flex gap-2">
              <Input
                placeholder="Код для отключения"
                inputMode="numeric"
                className="rounded-xl"
                value={totpCode}
                onChange={(e) => setTotpCode(e.target.value)}
              />
              <Button variant="outline" size="sm" className="rounded-xl self-center" onClick={disable2fa}>
                Выключить
              </Button>
            </div>
          </div>
        ) : totpSecret ? (
          <div className="space-y-2">
            <p className="text-xs text-muted-foreground">
              Добавьте секрет в Google Authenticator / Authy / 1Password
              (вручную или по URI), затем введите код:
            </p>
            <div className="rounded-xl bg-muted/60 p-3">
              <p className="text-[13px] sm:text-[11px] text-muted-foreground">Секрет:</p>
              <p className="break-all font-mono text-sm">{totpSecret.secret}</p>
              <p className="mt-2 break-all text-xs sm:text-[10px] text-muted-foreground">{totpSecret.uri}</p>
            </div>
            <div className="flex gap-2">
              <Input
                placeholder="000000"
                inputMode="numeric"
                className="rounded-xl text-center tracking-[0.3em]"
                value={totpCode}
                onChange={(e) => setTotpCode(e.target.value)}
              />
              <Button size="sm" className="rounded-xl self-center" onClick={enable2fa}>
                Подтвердить
              </Button>
            </div>
          </div>
        ) : (
          <Button variant="outline" size="sm" className="rounded-xl" onClick={setup2fa}>
            Включить 2FA
          </Button>
        )}
        {totpMsg && <p className="text-xs text-muted-foreground">{totpMsg}</p>}
      </DialogContent>
    </Dialog>
  );
}
