"use client";

import { useEffect, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { api } from "@/lib/api";
import { useAuth } from "@/components/auth";
import { Card, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { ProcessingStatus } from "@/components/processing-status";
import { StatusBadge } from "@/components/ui/badge";
import { ErrorState, SectionHeading } from "@/components/feedback";

export default function PoliciesPage() {
  const {user} = useAuth();
  const canReview = user?.role === "reviewer" || user?.role === "admin";
  const cache = useQueryClient();
  const policies = useQuery({queryKey: ["policies"], queryFn: api.policies});
  const [current, setCurrent] = useState("");
  const [file, setFile] = useState<File | null>(null);
  const [approvalSnapshot, setApprovalSnapshot] = useState<string[] | null>(null);
  useEffect(() => { if (!current && policies.data?.length) setCurrent(policies.data[0].policy_id); }, [current, policies.data]);
  const rules = useQuery({queryKey: ["policy-rules", current], queryFn: () => api.policyRules(current), enabled: !!current, refetchInterval: query => ["queued", "processing", "retry_wait"].includes(query.state.data?.extraction_status || "") ? 1500 : false});
  const upload = useMutation({mutationFn: api.uploadPolicy, onSuccess: data => { setCurrent(data.policy_id); setApprovalSnapshot(null); setFile(null); cache.invalidateQueries({queryKey: ["policies"]}); cache.invalidateQueries({queryKey: ["policy-rules", data.policy_id]}); }});
  const extraction = useMutation({mutationFn: () => api.extractPolicy(current), onSuccess: () => cache.invalidateQueries({queryKey: ["policy-rules", current]})});
  const decision = useMutation({mutationFn: ({id, action}: {id: string; action: "approve" | "reject"}) => api.decideRule(current, id, action), onSuccess: () => cache.invalidateQueries({queryKey: ["policy-rules", current]})});
  const batch = useMutation({mutationFn: () => api.approveAllRules(current, approvalSnapshot || []), onSuccess: () => {setApprovalSnapshot(null); cache.invalidateQueries({queryKey: ["policy-rules", current]}); cache.invalidateQueries({queryKey: ["my-profile"]});}});
  const pending = rules.data?.rules.filter(rule => rule.approval_status === "pending" && rule.verification_status === "verified") || [];
  const busy = upload.isPending || extraction.isPending || decision.isPending || batch.isPending;
  return <>
    <SectionHeading eyebrow="Evidence-backed compliance" title="Policy library" description="Upload a policy to automatically extract its rules, inspect the source evidence, then confirm approval. Reviewers and administrators decide which rules become active."/>
    <div className="grid gap-6 lg:grid-cols-[.8fr_1.4fr]">
      <div className="space-y-6">
        {canReview && <Card className="space-y-4 p-6"><CardTitle>Upload a policy</CardTitle><Input aria-label="Policy file" type="file" accept=".pdf,.docx,.pptx,.txt,.png,.jpg,.jpeg" onChange={e => setFile(e.target.files?.[0] || null)}/><Button disabled={!file || busy} onClick={() => file && upload.mutate(file)}>{upload.isPending ? "Uploading and extracting rules…" : "Upload policy"}</Button>{upload.isError && <ErrorState error={upload.error}/>}</Card>}
        <Card><CardHeader><CardTitle>Organization policies</CardTitle></CardHeader><div className="space-y-2 p-5 pt-0">
          {policies.isLoading ? <p role="status">Loading policies…</p> : policies.isError ? <ErrorState error={policies.error}/> : !policies.data?.length ? <p className="text-sm text-muted">No policies have been uploaded.</p> : policies.data.map(policy => <button className={`block w-full rounded-xl border p-4 text-left text-sm ${current === policy.policy_id ? "border-primary bg-[#f4f3ff]" : "border-stroke"}`} key={policy.policy_id} disabled={busy} onClick={() => {setCurrent(policy.policy_id); setApprovalSnapshot(null); decision.reset(); extraction.reset(); batch.reset();}}>{policy.filename}</button>)}
        </div></Card>
      </div>
      <Card><CardHeader><CardTitle>Source-backed rules</CardTitle></CardHeader><div className="space-y-4 px-6 pb-6">
        {current && <ProcessingStatus key={current} kind="policies" id={current}/>}
        {current && <a className="text-sm font-semibold text-primary" href={`/api/bridge/policies/${encodeURIComponent(current)}/original`}>Download original policy</a>}
        {current && <div className="space-y-3 rounded-xl border border-stroke p-4">
          <p role="status" className="text-sm">{rules.data?.extraction_message || "Automatic extraction runs when a policy is uploaded. Existing policies can be extracted below."}</p>
          {canReview && <><Button variant="secondary" disabled={busy || rules.data?.extraction_status === "processing"} onClick={() => {setApprovalSnapshot(null); extraction.mutate();}}>{extraction.isPending ? "Extracting all policy rules…" : "Retry whole-policy extraction"}</Button><p className="text-xs text-muted">Automatically reads the complete policy, up to 30,000 characters. Unsupported drafts are excluded; human approval is always required.</p></>}
          {extraction.isError && <ErrorState error={extraction.error}/>}
        </div>}
        {canReview && pending.length > 0 && <div className="space-y-3 rounded-xl border border-primary/30 bg-[#f4f3ff] p-4">
          <p className="text-sm font-semibold">{pending.length} verified rules awaiting your approval</p>
          {!approvalSnapshot ? <Button disabled={busy || pending.length > 100} onClick={() => {batch.reset(); setApprovalSnapshot(pending.map(rule => rule.id));}}>Approve all verified rules</Button> : <div className="space-y-3"><p className="text-sm">Approve all {approvalSnapshot.length} rules shown below? Confirm only after reviewing each condition and source quotation.</p><div className="flex gap-3"><Button disabled={busy} onClick={() => batch.mutate()}>Confirm approval of {approvalSnapshot.length} rules</Button><Button variant="secondary" disabled={busy} onClick={() => setApprovalSnapshot(null)}>Cancel</Button></div></div>}
          {batch.isError && <ErrorState error={batch.error}/>}
        </div>}
        {batch.isSuccess && <p role="status" className="text-sm text-green-700">All selected rules were approved.</p>}
        {decision.isError && <ErrorState error={decision.error}/>}
        {rules.isLoading ? <p role="status">Loading rules…</p> : rules.isError ? <ErrorState error={rules.error}/> : !rules.data?.rules.length ? <p className="text-sm text-muted">Select a policy with extracted rules. Missing rules do not establish compliance.</p> : rules.data.rules.map(rule => <div key={rule.id} className="space-y-3 rounded-xl border border-stroke p-5"><div className="flex flex-wrap items-center justify-between gap-3"><span className="font-mono text-sm">{rule.rule_id}</span><div className="flex gap-2"><StatusBadge status={rule.verification_status}/><StatusBadge status={rule.approval_status}/></div></div><p className="text-sm">{rule.rule_data.category} · {rule.rule_data.operator} {rule.rule_data.threshold} {rule.rule_data.currency} · {rule.rule_data.action}</p><blockquote dir="auto" className="border-l-2 border-primary pl-3 text-sm text-muted">{rule.rule_data.source_quote}</blockquote><p className="text-xs text-muted">Reviewer: {rule.approved_by_name || "Pending"}</p>{canReview && rule.approval_status === "pending" && <div className="flex gap-3"><Button size="sm" disabled={busy || !!approvalSnapshot || rule.verification_status !== "verified"} onClick={() => decision.mutate({id: rule.id, action: "approve"})}>Approve rule</Button><Button size="sm" variant="secondary" disabled={busy || !!approvalSnapshot} onClick={() => decision.mutate({id: rule.id, action: "reject"})}>Reject rule</Button></div>}</div>)}
        <p className="text-xs text-muted">Rule approval activates a verified policy rule. It does not approve any expense or payment.</p>
      </div></Card>
    </div>
  </>;
}
