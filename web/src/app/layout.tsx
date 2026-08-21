import type { Metadata } from "next";
import Link from "next/link";
import type { ReactNode } from "react";

import { Navigation } from "@/components/navigation";
import "./globals.css";

export const metadata: Metadata = {
  title: { default: "Job Market Analyzer", template: "%s · Job Market Analyzer" },
  description: "Local posting-level remote job market intelligence.",
};

export default function RootLayout({ children }: Readonly<{ children: ReactNode }>) {
  return (
    <html lang="en">
      <body>
        <a href="#main" className="skip-link">Skip to content</a>
        <div className="app-shell">
          <aside className="sidebar">
            <Link href="/" className="brand" aria-label="Job Market Analyzer overview">
              <span className="brand-mark" aria-hidden="true">JM</span>
              <span><strong>Job Market</strong><small>Analyzer / local</small></span>
            </Link>
            <Navigation />
            <div className="sidebar-note"><i aria-hidden="true" /><span>Read-only<br />Posting-level data</span></div>
          </aside>
          <main id="main">{children}</main>
        </div>
      </body>
    </html>
  );
}
