import type { Metadata } from "next";
import Link from "next/link";
import "./globals.css";

export const metadata: Metadata = {
  title: "BioAutoScientist",
  description: "ToolUniverse-native AI scientist workbench"
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body>
        <div className="shell">
          <header className="topbar">
            <Link href="/" className="brand">BioAutoScientist</Link>
            <nav className="nav">
              <Link href="/objectives/new">New Objective</Link>
              <Link href="/showcase">Showcase</Link>
              <Link href="/runs">Runs</Link>
              <Link href="/models">Models</Link>
              <Link href="/tools">Tool Inventory</Link>
              <Link href="/board">Research Board</Link>
            </nav>
          </header>
          {children}
        </div>
      </body>
    </html>
  );
}
