"use client";

import Link from "next/link";
import { useQuery } from "@tanstack/react-query";
import { ArrowRight, ArrowUpRight, BookOpenCheck, CheckCircle2, CircleAlert, CloudUpload, FileStack, LayoutDashboard, ScanText, ShieldCheck, Sparkles } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Card, CardHeader, CardTitle } from "@/components/ui/card";
import { SectionHeading, LoadingState, ErrorState, EmptyState } from "@/components/feedback";
import { DocumentsTable } from "@/components/documents-table";
import { api } from "@/lib/api";
import { formatDate } from "@/lib/utils";
import type { DocumentSummary } from "@/lib/types";

function activityDays(documents: DocumentSummary[]) {
  const now = new Date();
  return Array.from({ length: 7 }, (_, i) => {
    const date = new Date(now.getFullYear(), now.getMonth(), now.getDate() - 6 + i);
    const key = date.toDateString();
    return { key, day: new Intl.DateTimeFormat("en", { weekday: "short" }).format(date), count: documents.filter((d) => new Date(d.created_at).toDateString() === key).length };
  });
}

export default function Dashboard() {
  const docs = useQuery({ queryKey: ["documents"], queryFn: api.documents });
  const reviews = useQuery({ queryKey: ["pending-reviews"], queryFn: api.pendingReviews });
  const documents = docs.data || [];
  const pending = documents.filter((d) => ["needs_review", "auto_accepted"].includes(d.review_status)).length;
  const completed = documents.filter((d) => d.processing_status === "completed").length;
  const approved = documents.filter((d) => ["approved", "corrected"].includes(d.review_status)).length;
  const days = activityDays(documents);
  const max = Math.max(...days.map((d) => d.count), 1);
  const cards = [
    { label: "Total documents", value: documents.length, icon: FileStack, color: "bg-[#efefff] text-[#6864ec]", helper: "Files in your workspace" },
    { label: "Processed", value: completed, icon: CheckCircle2, color: "bg-[#e7f9f1] text-[#2b9f70]", helper: "Extraction completed" },
    { label: "Awaiting review", value: pending, icon: CircleAlert, color: "bg-[#fff4e4] text-[#d39337]", helper: "Require human verification" },
    { label: "Reviewed", value: approved, icon: ShieldCheck, color: "bg-[#e9f2ff] text-[#5187cc]", helper: "Approved or corrected" },
  ];

  return <>
    <SectionHeading eyebrow="Your workspace" title="Intelligence overview" description="A live view of documents processed through your FastAPI and Gemini extraction pipeline." action={<Button asChild><Link href="/upload"><CloudUpload size={17}/> Upload document</Link></Button>}/>
    <section aria-labelledby="overview-intro-title" className="relative mb-7 overflow-hidden rounded-[22px] bg-[#4545bb] px-7 py-7 text-white sm:px-9 sm:py-8" style={{backgroundImage: "linear-gradient(115deg, #37378f 0%, #4545bb 60%, #5752b8 100%)"}}>
      <div className="pointer-events-none absolute -right-10 -top-20 h-72 w-72 rounded-full border-[45px] border-white/[.045]"/>
      <div className="pointer-events-none absolute right-36 top-12 h-52 w-52 rounded-full bg-white/[.045] blur-2xl"/>
      <div className="relative z-10 flex flex-col items-start justify-between gap-5 sm:flex-row sm:items-center">
        <div>
          <div className="mb-2 flex items-center gap-2 text-[11px] font-bold uppercase tracking-[.2em] text-[#e3e4ff]"><Sparkles size={14}/> AI document intelligence</div>
          <h2 id="overview-intro-title" className="max-w-lg text-xl font-bold leading-snug tracking-tight text-white sm:text-2xl">From raw documents to reliable decisions.</h2>
          <p className="mt-2 max-w-xl text-[13px] leading-relaxed text-[#e3e4ff]">Extract with Gemini, trace evidence, and keep a human in control of important decisions.</p>
        </div>
        <Button asChild className="shrink-0 border-0 bg-white text-[#4c49b9] hover:bg-[#eff0ff]"><Link href="/upload">Process a file <ArrowRight size={16}/></Link></Button>
      </div>
    </section>
    {docs.isLoading ? <LoadingState/> : docs.isError ? <ErrorState error={docs.error} retry={() => docs.refetch()} /> : <>
      <div className="mb-7 grid gap-4 sm:grid-cols-2 2xl:grid-cols-4">{cards.map((card) => <Card key={card.label} className="flex items-start justify-between gap-3 p-5"><div><div className="text-[12px] font-medium text-muted">{card.label}</div><div className="mt-2 text-[31px] font-bold tracking-tight text-ink">{card.value}</div><div className="mt-2 text-[11px] text-[#9ba4b7]">{card.helper}</div></div><div className={`flex h-11 w-11 shrink-0 items-center justify-center rounded-[14px] ${card.color}`}><card.icon size={21}/></div></Card>)}</div>
      <div className="mb-7 grid gap-6 xl:grid-cols-[1.6fr_1fr]">
        <Card><CardHeader><div><CardTitle>Processing activity</CardTitle><p className="mt-1 text-[12px] text-muted">Documents uploaded over the past 7 days</p></div><span className="rounded-lg bg-[#f2f3fa] px-3 py-1.5 text-[11px] font-semibold text-muted">Last 7 days</span></CardHeader><div className="px-7 pb-6"><div className="flex h-44 items-end justify-between gap-3 border-b border-stroke pb-3">{days.map((day) => <div key={day.key} className="group flex h-full flex-1 flex-col items-center justify-end gap-3" title={`${day.count} documents — ${formatDate(day.key)}`}><div className="flex h-full w-full items-end justify-center"><div className="relative w-full max-w-[48px] rounded-t-[9px] bg-gradient-to-b from-[#7978f9] to-[#5b5ae7] transition-all group-hover:from-[#a19dff]" style={{ height: `${Math.max((day.count / max) * 100, 5)}%`, opacity: day.count === 0 ? .15 : 1 }}><span className="absolute -top-6 left-1/2 -translate-x-1/2 text-[11px] font-semibold text-ink opacity-0 group-hover:opacity-100">{day.count}</span></div></div></div>)}</div><div className="mt-3 flex justify-between gap-3">{days.map((d) => <span key={d.key} className="flex-1 text-center text-[11px] font-medium text-[#949db0]">{d.day}</span>)}</div></div></Card>
        <Card className="flex flex-col"><CardHeader><div><CardTitle>Quick actions</CardTitle><p className="mt-1 text-[12px] text-muted">Common tasks, one click away</p></div></CardHeader><div className="space-y-2 px-5 pb-5">{[
          { href: "/upload", icon: ScanText, title: "Analyze a document", sub: "Upload a PDF, image or Office file", tint: "bg-[#efefff] text-primary" },
          { href: "/reviews", icon: ShieldCheck, title: "Review extracted data", sub: `${reviews.data?.length ?? pending} documents waiting`, tint: "bg-[#fff5e7] text-[#c88735]" },
          { href: "/policies", icon: BookOpenCheck, title: "Upload company policy", sub: "Prepare source-backed rules", tint: "bg-[#eaf8f3] text-[#33a475]" },
        ].map(({ href, icon: Icon, title, sub, tint }) => <Link key={href} href={href} className="group flex items-center gap-3 rounded-xl p-3 hover:bg-[#f9f9fe]"><span className={`flex h-11 w-11 items-center justify-center rounded-[12px] ${tint}`}><Icon size={19}/></span><span className="flex-1"><span className="block text-[13px] font-semibold text-ink">{title}</span><span className="mt-1 block text-[11px] text-muted">{sub}</span></span><ArrowUpRight className="text-[#a5adbe] group-hover:text-primary" size={17}/></Link>)}</div></Card>
      </div>
      <div className="mb-4 flex items-center justify-between"><div><h2 className="text-[17px] font-bold tracking-tight">Recent documents</h2><p className="mt-1 text-[12px] text-muted">Most recently uploaded files and their statuses</p></div><Link href="/documents" className="inline-flex items-center gap-1.5 text-[12px] font-semibold text-primary hover:underline">View all <ArrowUpRight size={15}/></Link></div>
      {documents.length ? <DocumentsTable compact documents={documents}/> : <EmptyState title="Your workspace is ready" description="There are no documents yet. Upload your first file to begin extraction." action={<Button asChild><Link href="/upload">Upload your first document</Link></Button>}/>}
    </>}
  </>;
}
