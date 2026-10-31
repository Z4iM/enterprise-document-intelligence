import type { Metadata } from "next";
import "./globals.css";
import { Providers } from "@/components/providers";
import { SessionGate } from "@/components/auth";
import { AppShell } from "@/components/layout";

export const metadata: Metadata = {
  title: { default: "NEXUS EDI | Document Intelligence", template: "%s | NEXUS EDI" },
  description: "Enterprise Document Intelligence, review, and policy compliance workspace",
};

export default function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  const showcase = process.env.EDI_SHOWCASE_MODE === "synthetic-scripted";
  return <html lang="en"><body>{showcase && <aside aria-label="Synthetic showcase notice" className="border-b border-amber-200 bg-amber-50 px-4 py-2 text-center text-xs text-amber-950">Synthetic demo · Scripted model generation · Real authorization, human review and deterministic evaluation</aside>}<Providers><SessionGate><AppShell>{children}</AppShell></SessionGate></Providers></body></html>;
}
