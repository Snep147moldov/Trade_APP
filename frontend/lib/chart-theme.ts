import { ColorType } from "lightweight-charts";

/** Цвета графиков живут в CSS (--chart-*), но lightweight-charts рисует на
 *  canvas и переменную не понимает — ему нужно вычисленное значение. Читаем
 *  его в момент построения графика; при смене темы график пересоздаётся. */
function v(name: string, fallback: string): string {
  if (typeof window === "undefined") return fallback;
  const raw = getComputedStyle(document.documentElement)
    .getPropertyValue(name)
    .trim();
  return raw || fallback;
}

export function chartPalette() {
  return {
    up: v("--chart-up", "#1f9d55"),
    down: v("--chart-down", "#d93a30"),
    brand: v("--chart-brand", "#0a84ff"),
    warn: v("--chart-warn", "#d98200"),
    info: v("--chart-info", "#5856d6"),
    text: v("--chart-text", "#8a8a8f"),
    grid: v("--chart-grid", "rgba(0,0,0,0.05)"),
    cross: v("--chart-cross", "rgba(0,0,0,0.22)"),
    label: v("--chart-label", "#1c1c1e"),
  };
}

/** Общие настройки полотна: фон прозрачный, чтобы карточка задавала цвет сама
 *  и график не спорил с темой. */
export function chartBase() {
  const c = chartPalette();
  return {
    layout: {
      background: { type: ColorType.Solid, color: "transparent" },
      textColor: c.text,
      fontFamily:
        "-apple-system, BlinkMacSystemFont, 'SF Pro Text', 'Segoe UI', sans-serif",
      attributionLogo: false,
    },
    grid: {
      vertLines: { color: c.grid },
      horzLines: { color: c.grid },
    },
    rightPriceScale: { borderVisible: false },
    timeScale: {
      borderVisible: false,
      timeVisible: true,
      secondsVisible: false,
    },
    crosshair: {
      vertLine: { color: c.cross, labelBackgroundColor: c.label },
      horzLine: { color: c.cross, labelBackgroundColor: c.label },
    },
    autoSize: true,
  } as const;
}
