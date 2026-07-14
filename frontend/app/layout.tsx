import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "Codnixy AI Trade — торговый ассистент",
  description:
    "Форекс-ассистент на детерминированных формулах: технические индикаторы, ИИ-анализ новостей, строгий риск-менеджмент, уведомления в Telegram.",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="ru" className="h-full antialiased">
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
