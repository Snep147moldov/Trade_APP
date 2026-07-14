"use client";

import { useEffect, useState } from "react";
import { Badge } from "@/components/ui/badge";
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
import { Separator } from "@/components/ui/separator";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { api, type AuditEntry, type AuthUser } from "@/lib/api";

const ACTION_RU: Record<string, string> = {
  login_ok: "Вход",
  login_fail: "Неудачный вход",
  logout: "Выход",
  password_change: "Смена пароля",
  "2fa_enabled": "2FA включена",
  "2fa_disabled": "2FA выключена",
  watchlist_update: "Изменён список пар",
  signal_create: "Создан сигнал",
  settings_update: "Настройки стратегии",
  config_update: "Подключения",
  news_run: "Запуск ИИ-анализа",
  user_created: "Создан пользователь",
  user_deleted: "Удалён пользователь",
};

export function AdminDialog({ me }: { me: AuthUser }) {
  const [open, setOpen] = useState(false);
  const [users, setUsers] = useState<AuthUser[]>([]);
  const [audit, setAudit] = useState<AuditEntry[]>([]);
  const [newLogin, setNewLogin] = useState("");
  const [newPwd, setNewPwd] = useState("");
  const [newRole, setNewRole] = useState<"user" | "admin">("user");
  const [msg, setMsg] = useState<string | null>(null);

  const refresh = () => {
    api.users().then(setUsers).catch(() => {});
    api.auditLog().then(setAudit).catch(() => {});
  };

  useEffect(() => {
    if (open) refresh();
  }, [open]);

  const create = async () => {
    setMsg(null);
    try {
      await api.createUser(newLogin, newPwd, newRole);
      setNewLogin("");
      setNewPwd("");
      setMsg("✅ Пользователь создан.");
      refresh();
    } catch (e) {
      setMsg(`❌ ${e instanceof Error ? e.message.replace(/^\d+\s*/, "").slice(0, 120) : "ошибка"}`);
    }
  };

  const remove = async (id: number) => {
    try {
      await api.deleteUser(id);
      refresh();
    } catch {
      /* ignore */
    }
  };

  return (
    <Dialog open={open} onOpenChange={setOpen}>
      <DialogTrigger asChild>
        <Button variant="outline" size="sm" className="rounded-xl">
          Админ
        </Button>
      </DialogTrigger>
      <DialogContent className="max-h-[85vh] overflow-y-auto rounded-2xl sm:max-w-[720px]">
        <DialogHeader>
          <DialogTitle className="tracking-tight">Администрирование</DialogTitle>
          <DialogDescription>Пользователи и журнал действий</DialogDescription>
        </DialogHeader>

        <p className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">
          Пользователи
        </p>
        <div className="space-y-1.5">
          {users.map((u) => (
            <div key={u.id} className="flex items-center justify-between rounded-xl bg-muted/50 px-3 py-2">
              <div className="flex items-center gap-2">
                <span className="text-sm font-medium">{u.username}</span>
                <Badge variant="secondary" className="rounded-full text-[10px]">
                  {u.role === "admin" ? "админ" : "пользователь"}
                </Badge>
                {u.totp_enabled && (
                  <Badge variant="secondary" className="rounded-full bg-[#34c759]/10 text-[10px] text-[#34c759]">
                    2FA
                  </Badge>
                )}
              </div>
              {u.id !== me.id && (
                <Button variant="ghost" size="sm" className="h-7 rounded-lg text-xs text-[#ff3b30]"
                        onClick={() => remove(u.id)}>
                  Удалить
                </Button>
              )}
            </div>
          ))}
        </div>

        <div className="grid grid-cols-[1fr_1fr_auto_auto] items-end gap-2">
          <Input placeholder="Логин" className="rounded-xl" value={newLogin}
                 onChange={(e) => setNewLogin(e.target.value)} />
          <Input placeholder="Пароль (мин. 8)" type="password" className="rounded-xl" value={newPwd}
                 onChange={(e) => setNewPwd(e.target.value)} />
          <button
            className="h-9 rounded-xl bg-muted px-3 text-xs"
            onClick={() => setNewRole(newRole === "user" ? "admin" : "user")}
          >
            {newRole === "admin" ? "админ" : "пользователь"}
          </button>
          <Button size="sm" className="rounded-xl" onClick={create}
                  disabled={newLogin.length < 3 || newPwd.length < 8}>
            Создать
          </Button>
        </div>
        {msg && <p className="text-xs text-muted-foreground">{msg}</p>}

        <Separator />

        <p className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">
          Журнал действий
        </p>
        <Table>
          <TableHeader>
            <TableRow className="text-xs">
              <TableHead>Время</TableHead>
              <TableHead>Кто</TableHead>
              <TableHead>Действие</TableHead>
              <TableHead>Детали</TableHead>
              <TableHead>IP</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {audit.slice(0, 50).map((r) => (
              <TableRow key={r.id} className="text-xs">
                <TableCell className="whitespace-nowrap tabular-nums">
                  {r.created_at
                    ? new Date(r.created_at + "Z").toLocaleString("ru-RU", {
                        day: "2-digit", month: "2-digit", hour: "2-digit", minute: "2-digit",
                      })
                    : "—"}
                </TableCell>
                <TableCell>{r.username || "—"}</TableCell>
                <TableCell>{ACTION_RU[r.action] ?? r.action}</TableCell>
                <TableCell className="max-w-[220px] truncate text-muted-foreground">
                  {r.detail}
                </TableCell>
                <TableCell className="text-muted-foreground">{r.ip}</TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
      </DialogContent>
    </Dialog>
  );
}
