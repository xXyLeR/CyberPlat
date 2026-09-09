import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "Vantage Range",
  description: "Plataforma corporativa de treinamento em segurança ofensiva.",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="pt-BR">
      <body className="bg-base font-sans text-ink antialiased">{children}</body>
    </html>
  );
}
