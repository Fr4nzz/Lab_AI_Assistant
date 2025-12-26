import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "Lab Assistant AI",
  description: "Asistente de laboratorio para entrada de resultados",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="es">
      <body className="antialiased">
        {children}
      </body>
    </html>
  );
}
