import type { Metadata, Viewport } from "next";
import localFont from "next/font/local";
import { AdsProvider } from "@/components/ads";
import { AppShell } from "@/components/app-shell";
import { ErrorReporter } from "@/components/error-reporter";
import { ServiceWorkerRegister } from "@/components/service-worker-register";
import { adsConfig } from "@/lib/ads";
import { SITE_URL } from "@/lib/site";
import "./globals.css";

// Interface: IBM Plex Sans (clear tabular figures for doses). Page titles: Newsreader, a
// reference-book serif. Plex Mono for formulas and codes. Self-hosted Latin subsets (SIL OFL, see
// ./fonts): no build-time download, and Turbopack's Google loader fails on these families.
const plexSans = localFont({
  variable: "--font-plex-sans",
  src: [
    { path: "./fonts/ibm-plex-sans-latin-400-normal.woff2", weight: "400" },
    { path: "./fonts/ibm-plex-sans-latin-500-normal.woff2", weight: "500" },
    { path: "./fonts/ibm-plex-sans-latin-600-normal.woff2", weight: "600" },
  ],
  fallback: ["system-ui", "Segoe UI", "Roboto", "sans-serif"],
});
const plexMono = localFont({
  variable: "--font-plex-mono",
  src: [
    { path: "./fonts/ibm-plex-mono-latin-400-normal.woff2", weight: "400" },
    { path: "./fonts/ibm-plex-mono-latin-500-normal.woff2", weight: "500" },
  ],
  fallback: ["ui-monospace", "Consolas", "monospace"],
  preload: false,
});
const newsreader = localFont({
  variable: "--font-newsreader",
  src: "./fonts/newsreader-latin-wght-normal.woff2",
  weight: "200 800",
  fallback: ["Georgia", "serif"],
});

export const metadata: Metadata = {
  metadataBase: new URL(SITE_URL),
  title: { default: "VetRef: Veterinary Reference", template: "%s | VetRef" },
  description:
    "Veterinary drug reference, brands, calculators and education for veterinary professionals.",
  applicationName: "VetRef",
  appleWebApp: { capable: true, title: "VetRef", statusBarStyle: "default" },
  icons: { apple: "/icons/apple-touch-icon.png" },
};

export const viewport: Viewport = {
  width: "device-width",
  initialScale: 1,
  themeColor: [
    { media: "(prefers-color-scheme: light)", color: "#0b6e6e" },
    { media: "(prefers-color-scheme: dark)", color: "#0d1213" },
  ],
};

export default function RootLayout({ children }: LayoutProps<"/">) {
  return (
    <html
      lang="en"
      className={`${plexSans.variable} ${plexMono.variable} ${newsreader.variable} h-full antialiased`}
    >
      <body className="flex min-h-full flex-col">
        <AdsProvider config={adsConfig()}>
          <AppShell>{children}</AppShell>
        </AdsProvider>
        <ServiceWorkerRegister />
        <ErrorReporter />
      </body>
    </html>
  );
}
