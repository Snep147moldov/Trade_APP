import { TRANSLATIONS } from "./translations";

export type Target = "en" | "fr" | "de";

/** Словарь хранится как «русский оригинал -> [en, fr, de]»: так три перевода
 *  одной строки стоят рядом и видно, что какой-то забыли. Здесь кортежи
 *  разворачиваются в три карты, по одному разу при загрузке модуля. */
export const MESSAGES: Record<Target, Record<string, string>> = {
  en: {},
  fr: {},
  de: {},
};

for (const [ru, v] of Object.entries(TRANSLATIONS)) {
  if (v[0]) MESSAGES.en[ru] = v[0];
  if (v[1]) MESSAGES.fr[ru] = v[1];
  if (v[2]) MESSAGES.de[ru] = v[2];
}
