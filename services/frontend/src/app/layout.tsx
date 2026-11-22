import type { Metadata } from "next";
import { Atkinson_Hyperlegible_Next } from "next/font/google";
import Link from "next/link";
import { Suspense } from "react";

import { StatusLine, StatusLineFallback } from "@/components/status-line";

import "./globals.css";

const atkinson = Atkinson_Hyperlegible_Next({
  variable: "--font-sans",
  subsets: ["latin"],
  fallback: ["system-ui", "sans-serif"],
  adjustFontFallback: false, // Next has no metric overrides for this family
});

export const metadata: Metadata = {
  title: "AgroPilot",
  description: "Should I water this plot today, and for how long?",
};

export default function RootLayout({ children }: LayoutProps<"/">) {
  return (
    <html lang="en" className={`${atkinson.variable} antialiased`}>
      <body className="min-h-dvh bg-sky text-ink">
        <div className="mx-auto w-full max-w-[480px] px-4 pt-3 pb-10">
          <header className="flex items-center justify-between gap-3">
            <Link href="/" className="text-sm font-bold">
              AgroPilot
            </Link>
            <Suspense fallback={<StatusLineFallback />}>
              <StatusLine />
            </Suspense>
          </header>
          <main>{children}</main>
        </div>
      </body>
    </html>
  );
}
