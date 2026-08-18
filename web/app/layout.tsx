import type { Metadata, Viewport } from "next";
import { Inter, Space_Mono } from "next/font/google";
import "./globals.css";

const inter = Inter({
  subsets: ["latin"],
  variable: "--font-sans",
  display: "swap",
});

const spaceMono = Space_Mono({
  weight: ["400", "700"],
  subsets: ["latin"],
  variable: "--font-mono",
  display: "swap",
});

export const metadata: Metadata = {
  title: "Basir AI — Cek Meja Cafe",
  description:
    "Cek ketersediaan meja cafe secara real-time sebelum berangkat. Basir AI mendeteksi okupansi lewat computer vision — tanpa identifikasi wajah.",
  robots: "index, follow",
};

export const viewport: Viewport = {
  themeColor: "#1B140F",
  width: "device-width",
  initialScale: 1,
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="id" className={`${inter.variable} ${spaceMono.variable}`}>
      <body>{children}</body>
    </html>
  );
}
