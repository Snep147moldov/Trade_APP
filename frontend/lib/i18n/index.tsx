"use client";

import { createContext, useContext, useEffect, useMemo, useState } from "react";

import { MESSAGES } from "./messages";

export const LOCALES = ["en", "ru", "fr", "de"] as const;
export type Locale = (typeof LOCALES)[number];

export const LOCALE_NAMES: Record<Locale, string> = {
  en: "English",
  ru: "Русский",
  fr: "Français",
  de: "Deutsch",
};

const STORAGE_KEY = "fxnav-lang";
// отличаем «пользователь выбрал» от «мы угадали по браузеру»: угаданное
// уступает языку, сохранённому на сервере, выбранное — нет
const EXPLICIT_KEY = "fxnav-lang-set";

/** Текущий язык живёт в модуле, а не только в контексте React.
 *
 *  Строки встречаются не только в JSX: в массивах на уровне модуля, в
 *  обработчиках, в утилитах без хуков. Хук там недоступен, а прокидывать язык
 *  параметром через полсотни файлов — хуже. Провайдер синхронно пишет сюда
 *  выбранный язык и перемонтирует дерево, поэтому `tr()` одинаково работает и в
 *  компоненте, и за его пределами. */
let current: Locale = "ru";

export function getLocale(): Locale {
  return current;
}

function isLocale(v: string | null | undefined): v is Locale {
  return !!v && (LOCALES as readonly string[]).includes(v);
}

/** Значения подстановок приходят прямо из данных, где поля бывают пустыми. */
export type Sub = string | number | null | undefined;

/** Перевод по русскому оригиналу.
 *
 *  Ключ — сама русская строка, а не придуманный идентификатор: приложение
 *  написано по-русски, 514 строк пришлось бы переименовывать вручную, и любая
 *  опечатка в ключе молча отдавала бы пустоту. Промах по словарю возвращает
 *  оригинал — непереведённая строка видна как русская, а не как `nav.title`.
 *
 *  Подстановки нумерованные: `tr("Сигнал #{0} открыт", id)`. */
export function tr(ru: string, ...vars: Sub[]): string {
  const dict = current === "ru" ? null : MESSAGES[current as Exclude<Locale, "ru">];
  let s = (dict && dict[ru]) || ru;
  if (vars.length) {
    s = s.replace(/\{(\d+)\}/g, (m: string, i: string) => {
      const v = vars[Number(i)];
      return v === undefined || v === null ? "" : String(v);
    });
  }
  return s;
}

/** Язык, выбранный на сайте-витрине, приходит в адресе: домены разные, общего
 *  localStorage у них нет. Поддерживаем и `?lang=`, и `#lang=` — токен входа
 *  тоже приходит во фрагменте. */
function fromUrl(): Locale | null {
  if (typeof window === "undefined") return null;
  const q = new URLSearchParams(window.location.search).get("lang");
  if (isLocale(q)) return q;
  const h = window.location.hash.match(/(?:^#|&)lang=([a-z]{2})/);
  return isLocale(h?.[1]) ? (h![1] as Locale) : null;
}

/** Read at import, not inside an effect: AuthGate clears the handoff fragment
 *  in its own effect, and child effects run before the provider's — by then
 *  `#…&lang=de` is gone. Module code runs before any of them. */
const urlLocale: Locale | null = typeof window === "undefined" ? null : fromUrl();

function detect(): Locale {
  if (typeof window === "undefined") return "ru";
  if (urlLocale) return urlLocale;
  const saved = localStorage.getItem(STORAGE_KEY);
  if (isLocale(saved)) return saved;
  for (const nav of navigator.languages ?? [navigator.language]) {
    const code = nav.slice(0, 2).toLowerCase();
    if (isLocale(code)) return code;
  }
  return "en";
}

type Ctx = {
  locale: Locale;
  setLocale: (l: Locale) => void;
  /** Язык из профиля на сервере: применяется, только если пользователь ещё
   *  не выбирал язык сам — иначе чужое устройство перебивало бы выбор. */
  adoptServerLocale: (l: string | null | undefined) => void;
};
const I18nContext = createContext<Ctx>({
  locale: "ru",
  setLocale: () => {},
  adoptServerLocale: () => {},
});

export function useLocale(): Ctx {
  return useContext(I18nContext);
}

/** Хук для компонентов: сам `t` глобален, но подписка на контекст заставляет
 *  компонент перерисоваться при смене языка. */
export function useT(): typeof tr {
  useContext(I18nContext);
  return tr;
}

export function I18nProvider({ children }: { children: React.ReactNode }) {
  // на сервере и до гидратации — русский, как в исходниках: иначе разметка
  // сервера и клиента разойдутся и React выбросит предупреждение о гидратации
  const [locale, setLocaleState] = useState<Locale>("ru");
  const [ready, setReady] = useState(false);

  useEffect(() => {
    const l = detect();
    if (urlLocale) {
      // язык, принесённый с сайта-витрины, — такой же осознанный выбор,
      // как нажатие в настройках
      try {
        localStorage.setItem(EXPLICIT_KEY, "1");
      } catch {}
    }
    current = l;
    setLocaleState(l);
    setReady(true);
    try {
      localStorage.setItem(STORAGE_KEY, l);
    } catch {}
    // язык из адреса убираем, чтобы он не застревал в закладках
    if (urlLocale) {
      const u = new URL(window.location.href);
      u.searchParams.delete("lang");
      u.hash = u.hash.replace(/(^#|&)lang=[a-z]{2}/, "$1").replace(/^#&?/, "#").replace(/^#$/, "");
      window.history.replaceState(null, "", u.pathname + u.search + u.hash);
    }
  }, []);

  const value = useMemo<Ctx>(() => {
    const apply = (l: Locale, explicit: boolean) => {
      current = l;
      setLocaleState(l);
      try {
        localStorage.setItem(STORAGE_KEY, l);
        if (explicit) localStorage.setItem(EXPLICIT_KEY, "1");
      } catch {}
      document.documentElement.lang = l;
    };
    return {
      locale,
      setLocale: (l: Locale) => apply(l, true),
      adoptServerLocale: (l) => {
        let chosen = false;
        try {
          chosen = localStorage.getItem(EXPLICIT_KEY) === "1";
        } catch {}
        if (!chosen && isLocale(l) && l !== locale) apply(l, false);
      },
    };
  }, [locale]);

  useEffect(() => {
    if (!ready) return;
    document.documentElement.lang = locale;
    // <title> приходит из metadata в layout.tsx — это серверный компонент, он
    // про выбранный язык ничего не знает. Правим на клиенте, иначе вкладка
    // остаётся русской при любом языке интерфейса.
    document.title = tr("FX Navigator — торговый ассистент");
  }, [locale, ready]);

  // ключ по языку перемонтирует дерево: константы и мемоизированные значения,
  // посчитанные на старом языке, иначе остались бы непереведёнными
  return (
    <I18nContext.Provider value={value}>
      <div key={locale} className="contents">
        {children}
      </div>
    </I18nContext.Provider>
  );
}
