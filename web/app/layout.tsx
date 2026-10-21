import type { Metadata, Viewport } from "next";
import { Inter } from "next/font/google";

import { DashboardProvider } from "@/components/dashboard-provider";
import { installDurableSnapshotBackend } from "@/lib/snapshot-store";

import "./globals.css";

// Use a durable change-detection baseline when KV/Redis is configured.
// Without it the baseline lives in memory and resets on a cold start.
installDurableSnapshotBackend();

const inter = Inter({
  subsets: ["latin"],
  display: "swap",
  variable: "--font-inter",
});

export const metadata: Metadata = {
  title: "Executive Pulse",
  description:
    "A decision-first operating layer for time-constrained executives. What needs your attention, why it matters, and what is waiting on you.",
};

export const viewport: Viewport = {
  themeColor: "#f5f1e8",
  width: "device-width",
  initialScale: 1,
};

export default function RootLayout({
  children,
}: Readonly<{ children: React.ReactNode }>) {
  return (
    <html lang="en" className={inter.variable}>
      <body>
        <DashboardProvider>{children}</DashboardProvider>
      </body>
    </html>
  );
}
