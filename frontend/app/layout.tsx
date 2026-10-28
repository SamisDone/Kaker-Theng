import type { Metadata, Viewport } from "next";
import { IBM_Plex_Mono, Spectral, Tiro_Bangla } from "next/font/google";
import "./globals.css";

const tiro = Tiro_Bangla({ subsets: ["bengali", "latin"], weight: "400", variable: "--font-tiro-bangla", display: "swap" });
const spectral = Spectral({ subsets: ["latin"], weight: ["400", "600"], style: ["normal", "italic"], variable: "--font-spectral", display: "swap" });
const plex = IBM_Plex_Mono({ subsets: ["latin"], weight: "400", variable: "--font-plex-mono", display: "swap" });

// Where the site lives: link previews (Facebook, WhatsApp) need the
// picture's full address. NEXT_PUBLIC_SITE_URL for another address.
const SITE_URL = process.env.NEXT_PUBLIC_SITE_URL ?? "https://kaker-theng-api.onrender.com";
const TITLE = "কাকের ঠ্যাং · Kaker Theng";
const DESCRIPTION = "আপনার হাতের লেখা থেকে বাংলা আর ইংরেজি ফন্ট। A Bangla and English font from your handwriting.";

// The icons and the link-preview picture (public/) are made from the mark
// by backend/scripts/make_icons.py.
export const metadata: Metadata = {
  metadataBase: new URL(SITE_URL),
  title: TITLE,
  description: DESCRIPTION,
  icons: {
    icon: [
      { url: "/favicon.svg", type: "image/svg+xml" },
      { url: "/favicon.ico", sizes: "16x16 32x32 48x48" },
    ],
    apple: "/apple-touch-icon.png",
  },
  openGraph: {
    type: "website",
    url: "/",
    siteName: "কাকের ঠ্যাং · Kaker Theng",
    title: TITLE,
    description: DESCRIPTION,
    locale: "bn_BD",
    images: [{ url: "/og.png", width: 1200, height: 630, alt: "কাকের ঠ্যাং · Kaker Theng" }],
  },
  twitter: { card: "summary_large_image", title: TITLE, description: DESCRIPTION, images: ["/og.png"] },
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
