import type { Metadata, Viewport } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "Aurex — торговый ассистент",
  description:
    "Форекс-ассистент на детерминированных формулах: технические индикаторы, ИИ-анализ новостей, строгий риск-менеджмент, уведомления в Telegram.",
};

export const viewport: Viewport = {
  width: "device-width",
  initialScale: 1,
  // интерфейс кладётся под вырез и домашнюю полосу iPhone; отступы возвращаем
  // сами через env(safe-area-inset-*) там, где это нужно
  viewportFit: "cover",
  themeColor: [
    { media: "(prefers-color-scheme: light)", color: "#f6f7f9" },
    { media: "(prefers-color-scheme: dark)", color: "#1a1a1c" },
  ],
};

// Читаем сохранённую тему синхронно, пока браузер разбирает HTML, и ставим
// атрибут до первой отрисовки. useEffect тут не годится: он срабатывает уже
// после отрисовки, и пользователь успевает увидеть светлую тему поверх тёмной.
// "system" означает следовать настройке ОС и переключаться вместе с ней.
const THEME_SCRIPT = `(function(){try{
var s=localStorage.getItem("aurex-theme")||localStorage.getItem("codnixy-theme")||"system";
var d=window.matchMedia("(prefers-color-scheme: dark)");
var set=function(){document.documentElement.setAttribute("data-theme",
  s==="system"?(d.matches?"dark":"light"):s)};
set();
if(s==="system"&&d.addEventListener)d.addEventListener("change",set);
}catch(e){}})()`;

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html
      lang="ru"
      data-theme="light"
      className="h-full antialiased"
      suppressHydrationWarning
    >
      <head>
        <script dangerouslySetInnerHTML={{ __html: THEME_SCRIPT }} />
      </head>
      <body
        className="min-h-full"
        style={{
          fontFamily:
            "-apple-system, BlinkMacSystemFont, 'SF Pro Text', 'Segoe UI', Roboto, sans-serif",
        }}
      >
        {children}
      </body>
    </html>
  );
}
