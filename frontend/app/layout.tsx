import type { Metadata, Viewport } from "next";
import { IBM_Plex_Mono, Spectral, Tiro_Bangla } from "next/font/google";
import "./globals.css";

const tiro = Tiro_Bangla({ subsets: ["bengali", "latin"], weight: "400", variable: "--font-tiro-bangla", display: "swap" });
const spectral = Spectral({ subsets: ["latin"], weight: ["400", "600"], style: ["normal", "italic"], variable: "--font-spectral", display: "swap" });
const plex = IBM_Plex_Mono({ subsets: ["latin"], weight: "400", variable: "--font-plex-mono", display: "swap" });

export const metadata: Metadata = {
  title: "কাকের ঠ্যাং · Kaker Theng",
  description: "আপনার হাতের লেখা থেকে বাংলা আর ইংরেজি ফন্ট। A Bangla and English font from your handwriting.",
};

export const viewport: Viewport = {
  width: "device-width",
  initialScale: 1,
  themeColor: "#f4f0e6",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="bn" className={`${tiro.variable} ${spectral.variable} ${plex.variable}`}>
      <body>{children}</body>
    </html>
  );
}
