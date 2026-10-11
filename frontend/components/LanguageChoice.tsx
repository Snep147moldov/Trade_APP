"use client";

import { LOCALES, LOCALE_NAMES, useLocale, type Locale } from "@/lib/i18n";

/** Флаги нарисованы символами региона, а не картинками: язык — не страна,
 *  но узнаётся по флагу быстрее всего, а эмодзи не тянет за собой спрайт. */
const FLAG: Record<Locale, string> = {
  en: "🇬🇧",
  ru: "🇷🇺",
  fr: "🇫🇷",
  de: "🇩🇪",
};

export function LanguageChoice({ onPicked }: { onPicked?: (l: Locale) => void }) {
  const { locale, setLocale } = useLocale();
  return (
    <div className="glass grid grid-cols-4 gap-1 rounded-2xl p-1">
      {LOCALES.map((l) => (
        <button
          key={l}
          type="button"
          onClick={() => {
            setLocale(l);
            onPicked?.(l);
          }}
          className={`flex flex-col items-center gap-1 rounded-xl py-2.5 text-[13px] sm:text-[11px] transition-all duration-200 active:scale-95 ${
            locale === l
              ? "bg-brand font-medium text-white shadow-sm"
              : "text-muted-foreground hover:bg-accent hover:text-foreground"
          }`}
        >
          <span className="text-base leading-none">{FLAG[l]}</span>
          {LOCALE_NAMES[l]}
        </button>
      ))}
    </div>
  );
}
