"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { ArrowUpRight, CheckCircle2, ClipboardCheck, FileText, ShieldAlert, ShieldCheck, Sparkles } from "lucide-react";
import { api } from "@/lib/api";
import type { PendingReview } from "@/lib/types";
import { formatDate, labelize } from "@/lib/utils";
import { StatusBadge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardHeader, CardTitle } from "@/components/ui/card";
import { Input, Textarea } from "@/components/ui/input";
import { EmptyState, ErrorState, Field, LoadingState, SectionHeading } from "@/components/feedback";

export default function ReviewsPage() {
  const qc = useQueryClient();
  const pending = useQuery({ queryKey: ["pending-reviews"], queryFn: api.pendingReviews });
  const [selected, setSelected] = useState<string | null>(null);
  const [decision, setDecision] = useState<"approved" | "corrected" | "rejected">("approved");
  const [reviewer, setReviewer] = useState("");
  const [notes, setNotes] = useState("");
  const [corrections, setCorrections] = useState("{}");
  const [formError, setFormError] = useState("");
  useEffect(() => { if (typeof window !== "undefined") { const id = new URLSearchParams(window.location.search).get("document"); if (id) setSelected(id); } }, []);
  const active = pending.data?.find((r) => r.document_id === selected) || pending.data?.[0];
  const submitReview = useMutation({ mutationFn: async () => {
    if (!active) throw new Error("Choose a document for review.");
    if (!reviewer.trim()) throw new Error("Enter a reviewer name.");
    let patch: Record<string, unknown> | undefined;
    if (decision === "corrected") {
      try { const data: unknown = JSON.parse(corrections); if (!data || typeof data !== "object" || Array.isArray(data) || Object.keys(data).length === 0) throw new Error(); patch = data as Record<string, unknown>; }
      catch { throw new Error("Corrections must be a non-empty JSON object, e.g. {\"total\": \"$99.00\"}."); }
    }
    return api.review(active.document_id, { decision, reviewer: reviewer.trim(), notes: notes.trim(), corrections: patch });
  }, onSuccess: () => { setFormError(""); setSelected(null); setNotes(""); setCorrections("{}"); qc.invalidateQueries({ queryKey: ["pending-reviews"] }); qc.invalidateQueries({ queryKey: ["documents"] }); if (active) qc.invalidateQueries({ queryKey: ["document", active.document_id] }); } });

  return <>
    <SectionHeading eyebrow="Human oversight" title="Review center" description="Resolve uncertain extractions using your existing FastAPI document-review endpoint. Human decisions are recorded in the audit history."/>
    <div className="mb-6 grid gap-4 sm:grid-cols-3">{[
      { label: "Awaiting review", value: pending.data?.length ?? "—", icon: ShieldAlert, tint: "text-[#d38a35] bg-[#fff4e3]" },
      { label: "Decision types", value: "3", icon: ClipboardCheck, tint: "text-primary bg-[#efefff]" },
      { label: "Auditability", value: "Enabled", icon: ShieldCheck, tint: "text-[#2b986b] bg-[#e8f7f0]" },
    ].map(({ label, value, icon: Icon, tint }) => <Card key={label} className="flex items-center gap-4 p-5"><div className={`rounded-xl p-3 ${tint}`}><Icon size={20}/></div><div><div className="text-[11px] text-muted">{label}</div><div className="mt-1 text-xl font-bold tracking-tight">{value}</div></div></Card>)}</div>
    {pending.isLoading ? <LoadingState label="Fetching pending human reviews..."/> : pending.isError ? <ErrorState error={pending.error} retry={() => pending.refetch()}/> : !pending.data?.length ? <EmptyState title="Review queue is clear" description="Documents flagged by the classifier or LLM extraction will appear here." action={<Button asChild variant="secondary"><Link href="/documents">Browse documents</Link></Button>}/> : <div className="grid gap-6 xl:grid-cols-[1fr_1.2fr]">
      <Card className="min-w-0 overflow-hidden"><CardHeader><div><CardTitle>Waiting documents</CardTitle><p className="mt-1 text-[12px] text-muted">Select a document to examine and resolve</p></div><StatusBadge status="needs_review"/></CardHeader><div className="max-h-[650px] divide-y divide-[#f0f2f7] overflow-y-auto smooth-scrollbar">{pending.data.map((d) => <button key={d.document_id} onClick={() => { setSelected(d.document_id); submitReview.reset(); setFormError(""); }} className={`flex w-full items-start gap-3 p-5 text-left transition-colors ${active?.document_id === d.document_id ? "bg-[#f4f3ff]" : "hover:bg-[#fbfbff]"}`}><span className="rounded-xl bg-white p-2.5 text-primary ring-1 ring-stroke"><FileText size={19}/></span><div className="min-w-0 flex-1"><div className="truncate text-[13px] font-semibold text-ink">{d.filename}</div><div className="mt-1 text-[11px] text-muted">{labelize(d.document_type)} · {formatDate(d.created_at)}</div><div className="mt-2 text-[11px] font-medium text-[#98733b]">{d.classification_confidence == null ? "Confidence unknown" : `${Math.round(d.classification_confidence * 100)}% classification confidence`}</div></div><ArrowUpRight size={16} className="shrink-0 text-[#9ba4b7]"/></button>)}</div></Card>
      {active && <Card className="min-w-0"><CardHeader><div><CardTitle>Review decision</CardTitle><p className="mt-1 break-all text-[12px] text-muted">{active.filename}</p></div><Link href={`/documents/${active.document_id}`} title="Inspect full document" className="rounded-xl border border-stroke p-2.5 text-primary hover:bg-[#f4f3ff]"><ArrowUpRight size={19}/></Link></CardHeader><div className="space-y-5 px-6 pb-6"><div className="rounded-2xl border border-stroke bg-[#fcfdff] p-4"><div className="mb-3 flex items-center gap-2 text-[12px] font-semibold"><Sparkles size={16} className="text-primary"/>Extracted data</div>{active.structured_data && Object.keys(active.structured_data).length ? <div className="grid grid-cols-2 gap-4">{Object.entries(active.structured_data).map(([k, v]) => <div key={k} className="min-w-0"><div className="text-[11px] text-muted">{labelize(k)}</div><div className="mt-1 break-words text-[12px] font-semibold">{v == null ? "—" : typeof v === "object" ? JSON.stringify(v) : String(v)}</div></div>)}</div> : <p className="text-xs text-muted">No fields to display. Open the original document to inspect it.</p>}</div>
        <div><div className="mb-2 text-[12px] font-semibold text-[#424e66]">Review decision</div><div className="grid grid-cols-3 gap-2">{(["approved", "corrected", "rejected"] as const).map((choice) => <button key={choice} onClick={() => setDecision(choice)} className={`rounded-xl border px-2 py-3 text-[12px] font-semibold capitalize ${decision === choice ? "border-primary bg-[#f1f0ff] text-primary" : "border-stroke bg-white text-muted hover:border-[#c3c0fb]"}`}>{choice}</button>)}</div></div>
        <Field label="Reviewer name"><Input placeholder="Your name" value={reviewer} onChange={(e) => setReviewer(e.target.value)}/></Field>
        {decision === "corrected" && <Field label="Corrected fields (JSON object)"><Textarea rows={5} spellCheck={false} className="font-mono" value={corrections} onChange={(e) => setCorrections(e.target.value)} placeholder={'{"total": "$175.00"}'}/></Field>}
        <Field label="Reviewer notes (optional)"><Textarea rows={3} placeholder="Why did you make this decision?" value={notes} onChange={(e) => setNotes(e.target.value)}/></Field>
        {(formError || submitReview.isError) && <div role="alert" className="rounded-xl bg-[#fff2f4] p-3 text-[12px] text-[#b43b51]">{formError || submitReview.error?.message}</div>}
        {submitReview.isSuccess && <div role="status" className="flex items-center gap-2 rounded-xl bg-[#eefaf3] p-3 text-[12px] font-semibold text-[#278258]"><CheckCircle2 size={16}/>Decision saved</div>}
        <Button disabled={submitReview.isPending || !reviewer.trim()} className="w-full" onClick={() => { setFormError(""); submitReview.mutate(); }}><ShieldCheck size={17}/>{submitReview.isPending ? "Saving review…" : "Save review decision"}</Button>
        <p className="text-[11px] leading-relaxed text-[#9da5b5]">Development-only workflow. The backend currently trusts the supplied reviewer name and does not enforce authentication.</p>
      </div></Card>}
    </div>}
  </>;
}
