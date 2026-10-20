"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { useParams } from "next/navigation";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { ArrowLeft, BookOpenCheck, CheckCircle2, ClipboardCheck, Download, FileText, Fingerprint, ListChecks, ScrollText, ShieldCheck, Sparkles } from "lucide-react";
import { api } from "@/lib/api";
import type { ValidationResult } from "@/lib/types";
import { formatDate, formatSize, labelize, shortId } from "@/lib/utils";
import { Button } from "@/components/ui/button";
import { Card, CardHeader, CardTitle } from "@/components/ui/card";
import { StatusBadge } from "@/components/ui/badge";
import { Input } from "@/components/ui/input";
import { EmptyState, ErrorState, Field, LoadingState } from "@/components/feedback";

const keys = ["merchant", "vendor", "date", "total", "expense_category", "invoice_number", "payment_method", "name", "email"];

export default function DocumentDetailPage() {
  const { id } = useParams<{ id: string }>();
  const [tab, setTab] = useState<"fields" | "source" | "audit" | "reviews">("fields");
  const [policyId, setPolicyId] = useState("");
  const [validation, setValidation] = useState<ValidationResult | null>(null);
  const doc = useQuery({ queryKey: ["document", id], queryFn: () => api.document(id), enabled: !!id });
  const audit = useQuery({ queryKey: ["audit", id], queryFn: () => api.audit(id), enabled: !!id && tab === "audit" });
  const reviews = useQuery({ queryKey: ["reviews", id], queryFn: () => api.reviews(id), enabled: !!id && tab === "reviews" });
  const validate = useMutation({ mutationFn: () => api.validate(id, policyId.trim()), onSuccess: setValidation });
  useEffect(() => { try { setPolicyId(localStorage.getItem("edi_last_policy_id") || ""); } catch { /* Storage may be unavailable */ } }, []);

  if (doc.isLoading) return <LoadingState label="Loading document and extracted fields..."/>;
  if (doc.isError) return <ErrorState error={doc.error} retry={() => doc.refetch()}/>;
  if (!doc.data) return <EmptyState title="Document not found" description="This file could not be retrieved from FastAPI."/>;
  const d = doc.data;
  const structured = d.structured_data || {};
  const fields = [...Object.entries(structured).sort(([a], [b]) => (keys.indexOf(a) === -1 ? 100 : keys.indexOf(a)) - (keys.indexOf(b) === -1 ? 100 : keys.indexOf(b)))];

  return <div className="space-y-6">
    <div><Link href="/documents" className="mb-4 inline-flex items-center gap-2 text-[12px] font-semibold text-muted hover:text-primary"><ArrowLeft size={15}/> All documents</Link><div className="flex flex-wrap items-start justify-between gap-4"><div className="min-w-0"><div className="mb-2 flex flex-wrap items-center gap-2"><span className="text-[11px] font-bold uppercase tracking-[.15em] text-primary">Document details</span><StatusBadge status={d.review_status}/></div><h1 className="break-all text-[25px] font-bold tracking-tight text-ink sm:text-[30px]">{d.filename}</h1><p className="mt-2 font-mono text-[11px] text-[#98a2b5]">ID: {d.document_id}</p></div><Button asChild variant="secondary"><a href={api.originalUrl(id)} download><Download size={17}/> Original file</a></Button></div></div>
    <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">{[
      { label: "Document type", value: labelize(d.document_type), icon: FileText },
      { label: "Processing", value: labelize(d.processing_status), icon: CheckCircle2 },
      { label: "Confidence", value: d.classification_confidence == null ? "Unknown" : `${Math.round(d.classification_confidence * 100)}%`, icon: Sparkles },
      { label: "File size", value: formatSize(d.file_size_bytes), icon: Fingerprint },
    ].map(({ label, value, icon: Icon }) => <Card key={label} className="flex items-center gap-3 p-5"><div className="rounded-xl bg-[#f0efff] p-3 text-primary"><Icon size={20}/></div><div><div className="text-[11px] text-muted">{label}</div><div className="mt-1 text-[16px] font-bold text-ink">{value}</div></div></Card>)}</div>
    <div className="grid gap-6 xl:grid-cols-[1.5fr_1fr]">
      <Card className="min-w-0 overflow-hidden"><div className="flex overflow-x-auto border-b border-stroke px-4 pt-3">{[
        { id: "fields", label: "Extracted fields", icon: ListChecks },
        { id: "source", label: "Source text", icon: ScrollText },
        { id: "audit", label: "Audit trail", icon: ClipboardCheck },
        { id: "reviews", label: "Review history", icon: ShieldCheck },
      ].map(({ id: key, label, icon: Icon }) => <button key={key} onClick={() => setTab(key as typeof tab)} className={`-mb-px flex shrink-0 items-center gap-2 border-b-2 px-4 py-4 text-[12px] font-semibold transition-colors ${tab === key ? "border-primary text-primary" : "border-transparent text-muted hover:text-ink"}`}><Icon size={15}/>{label}</button>)}</div>
        <div className="p-6">{tab === "fields" && (fields.length ? <div className="grid gap-4 sm:grid-cols-2">{fields.map(([key, value]) => <div key={key} className="min-w-0 rounded-xl border border-[#edf0f6] bg-[#fcfdff] p-4"><div className="mb-2 text-[11px] font-semibold uppercase tracking-[.07em] text-[#919bb0]">{labelize(key)}</div><div className="break-words text-[13px] font-semibold text-ink">{value == null ? "—" : typeof value === "object" ? JSON.stringify(value, null, 2) : String(value)}</div></div>)}</div> : <p className="text-sm text-muted">No structured fields were saved for this document.</p>)}
          {tab === "source" && <div><div className="mb-3 text-[12px] text-muted">Text preview from the extraction API · {d.text_length} total characters</div><pre className="max-h-[500px] overflow-auto whitespace-pre-wrap break-words rounded-xl border border-stroke bg-[#fafbfe] p-5 font-mono text-[12px] leading-7 text-[#4b5671] smooth-scrollbar">{d.text_preview || "No source text available."}</pre><p className="mt-2 text-[11px] text-[#97a1b3]">Only the first 1,000 characters are available from this endpoint.</p></div>}
          {tab === "audit" && (audit.isLoading ? <LoadingState/> : audit.isError ? <ErrorState error={audit.error} retry={() => audit.refetch()}/> : audit.data?.length ? <div className="space-y-5">{audit.data.map((event) => <div key={event.id} className="flex gap-4"><div className="flex h-9 w-9 shrink-0 items-center justify-center rounded-full bg-[#f0efff] text-primary"><ClipboardCheck size={17}/></div><div className="min-w-0 flex-1 border-b border-[#f0f2f7] pb-4"><div className="text-[13px] font-semibold text-ink">{labelize(event.event_type)}</div><p className="mt-1 break-words text-[12px] text-muted">{event.message || "Event recorded"}</p><div className="mt-2 text-[11px] text-[#a1a9b8]">{formatDate(event.created_at, { dateStyle: "medium", timeStyle: "short" })}</div></div></div>)}</div> : <p className="text-sm text-muted">No audit events were returned.</p>)}
          {tab === "reviews" && (reviews.isLoading ? <LoadingState/> : reviews.isError ? <ErrorState error={reviews.error} retry={() => reviews.refetch()}/> : reviews.data?.length ? <div className="space-y-4">{reviews.data.map((r) => <div key={r.id} className="rounded-xl border border-stroke p-4"><div className="flex flex-wrap items-center justify-between gap-2"><StatusBadge status={r.decision}/><span className="text-[11px] text-muted">{formatDate(r.created_at)}</span></div><div className="mt-3 text-[12px] text-ink">Reviewed by <strong>{r.reviewer || "Unspecified reviewer"}</strong></div>{r.notes && <p className="mt-2 text-[12px] text-muted">{r.notes}</p>}{r.corrections && <pre className="mt-3 overflow-x-auto rounded-lg bg-[#f8f9fc] p-3 text-[11px]">{JSON.stringify(r.corrections, null, 2)}</pre>}</div>)}</div> : <p className="text-sm text-muted">No review decisions recorded yet.</p>)}
        </div></Card>
      <div className="space-y-6">
        <Card><CardHeader><div><CardTitle>Compliance evaluation</CardTitle><p className="mt-1 text-[12px] text-muted">Run deterministic checks against a selected policy&apos;s approved rules.</p></div><BookOpenCheck size={20} className="text-primary"/></CardHeader><div className="space-y-3 px-6 pb-6"><Field label="Policy ID"><Input placeholder="Paste an existing policy UUID" value={policyId} onChange={(e) => { setPolicyId(e.target.value); setValidation(null); }}/></Field><Button className="w-full" disabled={!policyId.trim() || validate.isPending} onClick={() => validate.mutate()}>{validate.isPending ? "Evaluating…" : "Evaluate approved rules"}</Button><p className="text-[11px] leading-relaxed text-[#96a0b2]">Only verified, human-approved rules are evaluated. This is not a full compliance certification.</p>{validate.isError && <p role="alert" className="rounded-lg bg-[#fff1f2] p-3 text-[12px] text-[#b9485a]">{validate.error.message}</p>}</div></Card>
        {validation && <Card className="overflow-hidden"><div className="flex items-center justify-between border-b border-stroke p-5"><div className="text-sm font-semibold">Evaluation #{validation.validation_id}</div><StatusBadge status={validation.status}/></div><div className="space-y-4 p-5"><p className="text-[12px] leading-relaxed text-muted">{validation.validation.summary}</p><div className="grid grid-cols-2 gap-3"><div className="rounded-xl bg-[#f6f7fc] p-3"><div className="text-xl font-bold">{validation.validation.rules_evaluated}</div><div className="text-[11px] text-muted">Rules evaluated</div></div><div className="rounded-xl bg-[#f6f7fc] p-3"><div className="text-xl font-bold">{validation.validation.applicable_rules}</div><div className="text-[11px] text-muted">Applicable</div></div></div>{validation.validation.rule_results.map((r) => <div key={r.rule_id} className="rounded-xl border border-stroke p-3"><div className="flex items-start justify-between gap-2"><div className="font-mono text-[11px] font-semibold text-ink">{r.rule_id}</div><StatusBadge status={r.applicable ? r.status : "not_applicable"}/></div><p className="mt-2 text-[12px] text-muted">{r.explanation}</p></div>)}{validation.validation.required_actions.length > 0 && <div className="rounded-xl bg-[#fff8e9] p-4"><div className="mb-2 text-[12px] font-semibold text-[#99651e]">Required actions</div>{validation.validation.required_actions.map((a, i) => <p className="text-[12px] text-[#876e4c]" key={i}>• {labelize(a)}</p>)}</div>}{validation.evidence.length > 0 && <div><div className="mb-2 text-[12px] font-semibold">Policy evidence</div>{validation.evidence.map((e) => <blockquote key={e.rule_id} className="mb-3 border-l-[3px] border-[#8b86f8] bg-[#f8f7ff] px-4 py-3 text-[12px] leading-relaxed text-[#59607d]">{e.source_quote}<div className="mt-2 font-mono text-[10px] text-[#9a98c5]">{e.rule_id}</div></blockquote>)}</div>}</div></Card>}
        <Card className="p-6"><div className="text-[13px] font-semibold text-ink">Document metadata</div><div className="mt-5 space-y-4">{[
          { label: "Uploaded", value: formatDate(d.created_at, { dateStyle: "medium", timeStyle: "short" }) },
          { label: "Extraction method", value: labelize(d.structured_extraction_method) },
          { label: "File type", value: labelize(d.detected_type) },
          { label: "SHA-256", value: shortId(d.file_hash) },
        ].map(({ label, value }) => <div key={label} className="flex flex-wrap items-center justify-between gap-2 text-[12px]"><span className="text-muted">{label}</span><span className="font-semibold text-ink">{value}</span></div>)}</div></Card>
        {d.review_status === "needs_review" && <div className="rounded-[18px] border border-[#ffe6bf] bg-[#fff9ed] p-5"><div className="flex gap-3"><ShieldCheck size={18} className="shrink-0 text-[#c38b33]"/><div><h3 className="text-[13px] font-semibold text-[#886127]">Human review required</h3><p className="mt-1 text-[12px] leading-relaxed text-[#a28760]">Classification or extraction needs verification before final decisions.</p><Button asChild variant="secondary" size="sm" className="mt-4"><Link href={`/reviews?document=${id}`}>Open review center</Link></Button></div></div></div>}
      </div>
    </div>
  </div>;
}
