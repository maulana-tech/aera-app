import type { Metadata } from "next";
import { Geist, Geist_Mono } from "next/font/google";
import "twenty-ui/style.css";
import "twenty-ui/theme-dark.css";
import "twenty-ui/theme-light.css";
import "./globals.css";

const geistSans = Geist({
  variable: "--font-geist-sans",
  subsets: ["latin"],
});

const geistMono = Geist_Mono({
  variable: "--font-geist-mono",
  subsets: ["latin"],
});

export const metadata: Metadata = {
  title: "SIGAP — Antrean keputusan",
  description:
    "Asisten otomatis respons gangguan pasokan. Menyelidiki dampak, menyusun pilihan, "
    + "mencoret yang melanggar aturan, lalu mengeksekusi ke SAP setelah disetujui.",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html
      lang="en"
      className={`dark ${geistSans.variable} ${geistMono.variable} h-full antialiased`}
    >
      <body className="min-h-full flex flex-col">{children}</body>
    </html>
  );
}
