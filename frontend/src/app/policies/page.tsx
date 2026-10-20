"use client";

import { useEffect, useState } from "react";
import { useMutation, useQuery } from "@tanstack/react-query";
import Link from "next/link";
import { ArrowRight, BookOpenCheck, CheckCircle2, CloudUpload, FileText, Info, LibraryBig, ListChecks, Search, ShieldCheck } from "lucide-react";
import { api, ApiError } from "@/lib/api";
import type { KnownPolicy } from "@/lib/types";
import { formatDate, labelize, shortId } from "@/lib/utils";
import { Button } from "@/components/ui/button";
import { StatusBadge } from "@/components/ui/badge";
import { Card, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { EmptyState, ErrorState, Field, LoadingState, SectionHeading } from "@/components/feedback";

const STORAGE = "edi_known_policies";
function readKnown(): KnownPolicy[] {
  try { const v: unknown = JSON.parse(localStorage.getItem(STORAGE) || "[]"); return Array.isArray(v) ? v.filter((a) => a && typeof a.policy_id === "string" && typeof a.filename === "string") as KnownPolicy[] : []; }
  catch { return []; }
}

export default function PoliciesPage() {
  const [policies, setPolicies] = useState<KnownPolicy[]>([]);
  const [current, setCurrent] = useState("");
  const [manual, setManual] = useState("");
  const [file, setFile] = useState<File | null>(null);
  const [message, setMessage] = useState("");
  useEffect(() => { const items = readKnown(); setPolicies(items); setCurrent(localStorage.getItem("edi_last_policy_id") || items[0]?.policy_id || ""); }, []);
  const choose = (id: string) => { setCurrent(id); try { localStorage.setItem("edi_last_policy_id", id); } catch { /* no storage */ } };
  const remember = (p: KnownPolicy) => { const all = [p, ...readKnown().filter((i) => i.policy_id !== p.policy_id)]; try { localStorage.setItem(STORAGE, JSON.stringify(all)); } catch { /* no storage */ } setPolicies(all); choose(p.policy_id); };
  const upload = useMutation({ mutationFn: api.uploadPolicy, onSuccess: (res) => { remember({ policy_id: res.policy_id, filename: res.filename, added_at: new Date().toISOString() }); setFile(null); setMessage(`Policy uploaded successfully · ${res.chunks_created} source chunks created.`); } });
  const rules = useQuery({ queryKey: ["policy-rules", current], queryFn: () => api.policyRules(current), enabled: !!current, retry: false });

  return <>
    <SectionHeading eyebrow="Evidence-backed compliance" title="Policy library" description="Upload policies to FastAPI and inspect verified candidate rules where the optional rule-list API is available."/>
    <div className="mb-6 rounded-2xl border border-[#dfe9ff] bg-[#f4f7ff] p-4 text-[12px] leading-relaxed text-[#56719d]"><Info size={17} className="mr-2 inline align-[-3px]"/><strong>Important:</strong> The backend does not currently expose a policy-list endpoint. Policies displayed below are browser-local bookmarks, not a complete authoritative database listing.</div>
    <div className="grid gap-6 xl:grid-cols-[.9fr_1.4fr]">
      <div className="space-y-6"><Card><CardHeader><div><CardTitle>Add a company policy</CardTitle><p className="mt-1 text-[12px] text-muted">Document text is extracted and chunked by FastAPI.</p></div><CloudUpload size={21} className="text-primary"/></CardHeader><div className="space-y-4 px-6 pb-6"><Field label="Select policy file"><Input type="file" accept=".pdf,.docx,.pptx,.png,.jpg,.jpeg" className="h-auto cursor-pointer p-2.5 text-[12px]" onChange={(e) => { setFile(e.target.files?.[0] || null); setMessage(""); }}/></Field><Button disabled={!file || upload.isPending} className="w-full" onClick={() => { if (file) upload.mutate(file); }}><CloudUpload size={17}/>{upload.isPending ? "Processing policy…" : "Upload policy"}</Button>{upload.isError && <p role="alert" className="rounded-xl bg-[#fff1f2] p-3 text-[12px] text-[#b33d52]">{upload.error.message}</p>}{message && <p role="status" className="rounded-xl bg-[#eefaf3] p-3 text-[12px] font-medium text-[#228459]">{message}</p>}</div></Card>
        <Card><CardHeader><div><CardTitle>Open an existing policy</CardTitle><p className="mt-1 text-[12px] text-muted">Paste a policy ID from your database or Swagger.</p></div><Search size={20} className="text-primary"/></CardHeader><div className="space-y-3 px-6 pb-6"><Field label="Policy UUID"><Input placeholder="e.g. 153b2620-…" value={manual} onChange={(e) => setManual(e.target.value)}/></Field><Button className="w-full" variant="secondary" disabled={!manual.trim()} onClick={() => { remember({ policy_id: manual.trim(), filename: "Existing policy (manual ID)", added_at: new Date().toISOString() }); setManual(""); }}>Save policy bookmark <ArrowRight size={16}/></Button></div></Card>
        <Card><CardHeader><div><CardTitle>Saved policy bookmarks</CardTitle><p className="mt-1 text-[12px] text-muted">Stored in this browser only</p></div><LibraryBig size={19} className="text-primary"/></CardHeader><div className="divide-y divide-[#f0f2f7]">{policies.length ? policies.map((p) => <button key={p.policy_id} onClick={() => choose(p.policy_id)} className={`flex w-full items-center gap-3 p-5 text-left ${p.policy_id === current ? "bg-[#f7f6ff]" : "hover:bg-[#fafbff]"}`}><div className="rounded-xl bg-[#efefff] p-2.5 text-primary"><BookOpenCheck size={19}/></div><div className="min-w-0 flex-1"><div className="truncate text-[12px] font-semibold text-ink">{p.filename}</div><div className="mt-1 font-mono text-[10px] text-muted">{shortId(p.policy_id)} · {formatDate(p.added_at)}</div></div><ArrowRight size={16} className="text-[#929ab0]"/></button>) : <p className="px-6 pb-6 text-[12px] text-muted">Upload a policy or paste a known ID to get started.</p>}</div></Card></div>
      <div className="space-y-6"><Card className="overflow-hidden"><CardHeader><div><CardTitle>Source-verified policy rules</CardTitle><p className="mt-1 break-all font-mono text-[11px] text-muted">{current ? `Policy: ${current}` : "Choose a policy to inspect its rules"}</p></div><ShieldCheck size={21} className="text-primary"/></CardHeader>
        {!current ? <div className="px-6 pb-6"><div className="rounded-xl bg-[#f8f9fc] p-6 text-center text-[12px] text-muted">Select or upload a policy to inspect its candidates.</div></div> : rules.isLoading ? <div className="px-6 pb-6"><LoadingState label="Retrieving stored rules..."/></div> : rules.isError ? <div className="px-6 pb-6">{rules.error instanceof ApiError && rules.error.status === 404 ? <div className="rounded-xl border border-[#e2eaff] bg-[#f6f8ff] p-5"><div className="flex items-center gap-2 text-[13px] font-semibold text-[#466ca9]"><Info size={17}/> Rule-list endpoint not yet available</div><p className="mt-2 text-[12px] leading-relaxed text-[#647fae]">The GitHub main branch does not have GET /policies/&#123;policy_id&#125;/rules. Your local newer backend may support it. Uploading policies still works.</p></div> : <ErrorState error={rules.error} retry={() => rules.refetch()}/>}</div> : !rules.data?.rules.length ? <div className="px-6 pb-6"><div className="rounded-xl bg-[#f8f9fc] p-6 text-center text-[12px] text-muted">No stored rules returned. Extract and verify candidates through the backend workflow first.</div></div> : <div className="space-y-4 px-6 pb-6">{rules.data.rules.map((r) => <div key={r.id} className="rounded-xl border border-stroke p-5"><div className="flex flex-wrap items-center justify-between gap-3"><div className="font-mono text-[12px] font-semibold text-ink">{r.rule_id}</div><div className="flex items-center gap-2"><StatusBadge status={r.verification_status}/><StatusBadge status={r.approval_status}/></div></div><div className="mt-4 grid grid-cols-2 gap-3 text-[12px]"><div><span className="text-muted">Category</span><div className="mt-1 font-semibold">{labelize(r.rule_data.category)}</div></div><div><span className="text-muted">Action</span><div className="mt-1 font-semibold">{labelize(r.rule_data.action)}</div></div><div><span className="text-muted">Threshold</span><div className="mt-1 font-semibold">{r.rule_data.operator} {r.rule_data.threshold} {r.rule_data.currency}</div></div><div><span className="text-muted">Reviewer</span><div className="mt-1 font-semibold">{r.approved_by || "Awaiting approval"}</div></div></div><div className="mt-4 border-l-[3px] border-[#928dfa] bg-[#f9f8ff] px-3 py-2.5 text-[12px] leading-relaxed text-[#616a86]">{r.rule_data.source_quote}</div></div>)}<p className="text-[11px] leading-relaxed text-muted">Policy-rule approval is intentionally not exposed in this frontend until proper authentication and reviewer authorization exist.</p></div>}
      </Card>
      <Card className="p-6"><div className="flex gap-3"><div className="rounded-xl bg-[#eff6ff] p-3 text-[#5185bd]"><ListChecks size={21}/></div><div><h3 className="text-[13px] font-semibold">Validate your documents</h3><p className="mt-1 text-[12px] leading-relaxed text-muted">Once the company policy has approved rules, open a document and run a source-backed evaluation against its policy ID.</p><Button asChild variant="secondary" size="sm" className="mt-4"><Link href="/documents">Browse documents <ArrowRight size={15}/></Link></Button></div></div></Card>
      </div>
    </div>
  </>;
}
