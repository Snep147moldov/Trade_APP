"use client";

import { useId, useState } from "react";
import { Eye, EyeOff } from "lucide-react";

import { Input } from "@/components/ui/input";
import { cn } from "@/lib/utils";

/** Поле пароля с показом по глазу.
 *
 *  Вслепую набранный пароль — самая частая причина «не пускает»: длинный ключ
 *  MetaApi или пароль MT5 проверить было нечем, оставалось стирать и вводить
 *  заново. Кнопка не влияет на `value`, меняется только тип поля. */
export function PasswordInput({
  className,
  ...props
}: React.ComponentProps<typeof Input>) {
  const [shown, setShown] = useState(false);
  const id = useId();

  return (
    <div className="relative">
      <Input
        {...props}
        id={props.id ?? id}
        type={shown ? "text" : "password"}
        // место под кнопку, иначе длинное значение уезжает под неё
        className={cn("pr-10", className)}
      />
      <button
        type="button"
        // из табуляции исключена: между полем и кнопкой «Войти» лишняя
        // остановка мешает вводу с клавиатуры
        tabIndex={-1}
        onClick={() => setShown((v) => !v)}
        aria-label={shown ? "Скрыть пароль" : "Показать пароль"}
        title={shown ? "Скрыть пароль" : "Показать пароль"}
        className="absolute inset-y-0 right-0 flex w-10 items-center justify-center rounded-r-xl text-muted-foreground transition-colors hover:text-foreground"
      >
        {shown ? <EyeOff className="h-4 w-4" /> : <Eye className="h-4 w-4" />}
      </button>
    </div>
  );
}
