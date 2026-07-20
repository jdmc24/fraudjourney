import type { Metadata } from "next";
import { IBM_Plex_Mono, Outfit } from "next/font/google";
import type { ReactNode } from "react";

import "./globals.css";

const outfit = Outfit({
  subsets: ["latin"],
  weight: ["400", "500", "600", "700", "800"],
  variable: "--font-outfit",
  display: "swap"
});

const ibmPlexMono = IBM_Plex_Mono({
  subsets: ["latin"],
  weight: ["400", "500", "600", "700"],
  variable: "--font-ibm-plex-mono",
  display: "swap"
});

export const metadata: Metadata = {
  title: "Fraud Dispute Agent",
  description: "A regulated fraud dispute resolution agent reference build."
};

export default function RootLayout({ children }: Readonly<{ children: ReactNode }>) {
  return (
    <html lang="en">
      <body className={`${outfit.variable} ${ibmPlexMono.variable}`}>{children}</body>
    </html>
  );
}
