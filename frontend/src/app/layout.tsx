import type { Metadata } from "next";
import "./globals.css";
import { Providers } from "@/components/providers";
import { AppShell } from "@/components/layout";

export const metadata: Metadata = {
  title: { default: "NEXUS EDI | Document Intelligence", template: "%s | NEXUS EDI" },
  description: "Enterprise Document Intelligence, review, and policy compliance workspace",
};

export default function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  return <html lang="en"><body><Providers><AppShell>{children}</AppShell></Providers></body></html>;
}
