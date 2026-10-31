"use client";

import { ProfileMenu } from "@/components/profile-menu";
import { useAuth } from "@/components/auth";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { Activity, ArrowUpRight, BookOpenCheck, BrainCircuit, ChevronRight, FileStack, FileSearch, LayoutDashboard, Menu, ScanText, ShieldCheck, Sparkles, X } from "lucide-react";
import { useQuery } from "@tanstack/react-query";
import { useState } from "react";
import { api } from "@/lib/api";
import { cn } from "@/lib/utils";

const nav = [
  { href: "/", label: "Overview", icon: LayoutDashboard },
  { href: "/documents", label: "Documents", icon: FileStack },
  { href: "/upload", label: "New upload", icon: ScanText },
  { href: "/reviews", label: "Review center", icon: ShieldCheck },
  { href: "/policies", label: "Policy library", icon: BookOpenCheck },
  { href: "/investigate", label: "AI Investigation", icon: FileSearch },
  { href: "/workflows", label: "Agent workflows", icon: BrainCircuit },
  { href: "/operations", label: "Operations", icon: Activity },
];

function Sidebar({ close }: { close?: () => void }) {
  const {user} = useAuth();
  const pathname = usePathname();
  return <div className="flex h-full flex-col bg-[#111728] text-[#a6aec3]">
    <div className="flex h-[90px] items-center gap-3 border-b border-white/[.075] px-7">
      <div className="flex h-10 w-10 items-center justify-center rounded-[13px] bg-gradient-to-br from-[#8d88ff] to-[#4c58e5] text-white shadow-lg shadow-[#5a5af5]/25"><ScanText size={21} strokeWidth={2.1} /></div>
      <div><div className="text-[16px] font-extrabold tracking-[.035em] text-white">NEXUS <span className="text-[#a9a6ff]">EDI</span></div><div className="text-[10px] font-medium tracking-[.15em] text-[#77829d]">INTELLIGENCE PLATFORM</div></div>
    </div>
    <div className="px-5 pt-8"><div className="mb-3 px-3 text-[10px] font-bold uppercase tracking-[.19em] text-[#65728b]">Workspace</div>
      <nav className="space-y-1.5" aria-label="Primary navigation">{nav.filter(item => item.href !== "/operations" || user?.role === "admin").map(({ href, label, icon: Icon }) => {
        const active = href === "/" ? pathname === href : pathname === href || pathname.startsWith(href + "/");
        return <Link key={href} href={href} onClick={close} className={cn("group flex h-[44px] items-center gap-3 rounded-[11px] px-3.5 text-[13px] font-medium transition-all", active ? "bg-[#262d48] text-white shadow-inner ring-1 ring-white/[.05]" : "hover:bg-white/[.055] hover:text-white") }>
          <Icon size={18} strokeWidth={1.8} className={active ? "text-[#a8a2ff]" : "text-[#7b86a1] group-hover:text-white"}/><span>{label}</span>{active && <ChevronRight size={14} className="ml-auto text-[#848fa9]" />}
        </Link>;
      })}</nav>
    </div>
    <div className="mt-auto px-5 pb-7 pt-6"><div className="relative overflow-hidden rounded-2xl border border-[#3b4160] bg-gradient-to-br from-[#252b4c] to-[#1d233d] p-4">
      <div className="absolute -right-5 -top-6 h-28 w-28 rounded-full bg-[#776df9]/10 blur-lg"/><Sparkles size={19} className="mb-3 text-[#ada8ff]" />
      <div className="text-[13px] font-semibold text-white">Human-centered AI</div><p className="mt-1.5 text-xs leading-relaxed text-[#9ca5c0]">Verified evidence. Transparent decisions. Human oversight.</p>
      <div className="mt-3 inline-flex items-center gap-1.5 text-[11px] font-semibold text-[#bbb7ff]">Development workspace <ArrowUpRight size={12} /></div>
    </div></div>
  </div>;
}

function Topbar() {
  const pathname = usePathname();
  const [mobileOpen, setMobileOpen] = useState(false);
  const title = nav.find((n) => pathname === n.href || (n.href !== "/" && pathname.startsWith(n.href + "/")))?.label || "Documents";
  const status = useQuery({ queryKey: ["api-health"], queryFn: api.health, refetchInterval: 30_000, retry: 0 });
  const online = status.isSuccess && status.data.status === "healthy";
  return <>
    <header className="sticky top-0 z-20 flex h-[76px] items-center justify-between border-b border-stroke bg-white/95 px-5 backdrop-blur-md sm:px-8 lg:px-10">
      <div className="flex items-center gap-4"><button aria-label="Open navigation" className="rounded-lg border border-stroke p-2 text-ink lg:hidden" onClick={() => setMobileOpen(true)}><Menu size={20}/></button><div className="hidden text-[13px] font-medium text-[#9ba4b7] sm:block">Workspace <ChevronRight size={14} className="mx-1 inline" /></div><div className="text-sm font-semibold text-ink">{title}</div></div>
      <div className="flex items-center gap-4"><span className={cn("flex items-center gap-2 rounded-full border px-3 py-1.5 text-[11px] font-semibold", online ? "border-[#c8ecdd] bg-[#f0faf5] text-[#268463]" : "border-[#ffdfb2] bg-[#fff8ef] text-[#ac7329]")}><span className={cn("h-1.5 w-1.5 rounded-full", online ? "bg-[#36b781]" : "bg-[#eea84a]")}/>{online ? "API Connected" : status.isLoading ? "Checking API" : "API Offline"}</span><div className="hidden h-8 w-[1px] bg-stroke sm:block"/><ProfileMenu/></div>
    </header>
    {mobileOpen && <div className="fixed inset-0 z-50 lg:hidden"><div className="absolute inset-0 bg-[#08101e]/70" onClick={() => setMobileOpen(false)} /><div className="absolute inset-y-0 left-0 w-[272px]"><Sidebar close={() => setMobileOpen(false)} /></div><button className="absolute right-5 top-5 rounded-xl bg-white p-2 text-ink" aria-label="Close navigation" onClick={() => setMobileOpen(false)}><X size={20}/></button></div>}
  </>;
}

export function AppShell({ children }: { children: React.ReactNode }) {
  return <div className="min-h-screen bg-canvas text-ink"><aside className="fixed inset-y-0 left-0 z-30 hidden w-[252px] lg:block"><Sidebar /></aside><div className="lg:pl-[252px]"><Topbar/><main className="mx-auto max-w-[1440px] px-5 pb-14 pt-8 sm:px-8 lg:px-10 lg:pt-10">{children}</main><footer className="mx-auto max-w-[1440px] px-5 pb-8 text-[11px] text-[#9aa2b3] sm:px-8 lg:px-10">NEXUS EDI · Reviewed fields and source-backed policy decisions</footer></div></div>;
}
