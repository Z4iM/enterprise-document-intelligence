"use client";

import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { request } from "@/lib/api";
import { useAuth } from "@/components/auth";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";

type IndexState = {state: string; enabled: boolean; mode: string; passage_count: number; job_state: string | null; error: string | null};
type Citation = {citation_id: string; policy_id: string; filename: string; chunk_id: string; chunk_index: number; start: number; end: number; quote: string; language: string; source_verified: boolean; original_url: string};
type SearchResult = {status: string; results: Citation[]; mode: string; warning: string | null; stale_passages_excluded: number; latency_ms: number};

export function PolicyEvidenceSearch({policyId}: {policyId: string}) {
  const {user} = useAuth();
  const staff = user?.role === "reviewer" || user?.role === "admin";
  const cache = useQueryClient();
  const [query, setQuery] = useState("");
  const [confirmRemove, setConfirmRemove] = useState(false);
  const index = useQuery({queryKey: ["search-index", policyId], queryFn: () => request<IndexState>(`/policies/${encodeURIComponent(policyId)}/index`),
    refetchInterval: state => ["queued", "running", "retry_wait"].includes(state.state.data?.job_state || "") ? 1500 : false});
  const search = useMutation({mutationKey: ["policy-evidence", policyId], mutationFn: () => request<SearchResult>("/evidence/search", {method: "POST", headers: {"Content-Type": "application/json"}, body: JSON.stringify({query: query.trim(), policy_ids: [policyId], limit: 5})})});
  const update = useMutation({mutationFn: () => request(`/policies/${encodeURIComponent(policyId)}/index`, {method: "POST"}), onSuccess: () => cache.invalidateQueries({queryKey: ["search-index", policyId]})});
  const remove = useMutation({mutationFn: () => request(`/policies/${encodeURIComponent(policyId)}/index/remove`, {method: "POST"}), onSuccess: () => {setConfirmRemove(false); search.reset(); cache.invalidateQueries({queryKey: ["search-index", policyId]});}});
  const pending = ["queued", "running", "retry_wait"].includes(index.data?.job_state || "") && index.data?.enabled;
  const busy = update.isPending || remove.isPending;
  return <section aria-label="Search policy evidence" className="space-y-3 rounded-xl border border-stroke bg-[#fafbfe] p-4">
    <h3 className="font-semibold">Search policy evidence</h3>
    <p className="text-xs text-muted">Ask in English or Arabic. Results quote the original policy; they do not establish approval or compliance.</p>
    <p role="status" className="text-xs text-muted">{index.isLoading ? "Loading search status…" : pending ? "Preparing policy search…" : index.data?.state === "ready" ? `${index.data.mode === "hybrid" ? "Semantic + keyword" : "Keyword"} index · ${index.data.passage_count} passages` : index.data?.state === "removed" ? "This policy is excluded from search." : index.data?.state === "failed" ? "Search preparation failed. A reviewer can retry." : "Search is not prepared yet. A reviewer can index this policy."}</p>
    <form className="flex gap-2" onSubmit={event => {event.preventDefault(); search.mutate();}}>
      <Input aria-label="Policy evidence query" dir="auto" value={query} maxLength={500} placeholder="When is manager approval required? / متى أحتاج موافقة المدير؟" onChange={event => setQuery(event.target.value)}/>
      <Button disabled={!query.trim() || search.isPending || !index.data?.enabled || busy} type="submit">{search.isPending ? "Searching…" : "Search"}</Button>
    </form>
    {staff && <div className="flex flex-wrap gap-2">
      <Button size="sm" variant="secondary" disabled={busy || !!pending} onClick={() => update.mutate()}>{update.isPending ? "Queuing…" : "Update search index"}</Button>
      {index.data?.enabled && !confirmRemove && <Button size="sm" variant="secondary" disabled={busy} onClick={() => setConfirmRemove(true)}>Remove from search</Button>}
    </div>}
    {confirmRemove && <div className="space-y-2 text-xs"><p>Remove this policy from search results? The original policy and approved rules stay available.</p><Button size="sm" disabled={busy} onClick={() => remove.mutate()}>Confirm removal from search</Button><Button size="sm" variant="secondary" disabled={busy} onClick={() => setConfirmRemove(false)}>Cancel</Button></div>}
    {(index.isError || search.isError || update.isError || remove.isError) && <p role="alert" className="text-xs text-red-700">{search.error?.message || update.error?.message || remove.error?.message || "Could not load search status."}</p>}
    {search.data && <div className="space-y-3">
      <p role="status" className="text-xs text-muted">{search.data.status === "no_evidence" ? "No supporting evidence found. Do not infer permission from missing results." : `${search.data.results.length} source passages · ${search.data.mode === "hybrid" ? "semantic + keyword" : "keyword"} retrieval`}</p>
      {search.data.warning && <p className="text-xs text-amber-800">{search.data.warning}</p>}
      {search.data.stale_passages_excluded > 0 && <p className="text-xs text-amber-800">Changed source passages were excluded. Ask a reviewer to update the search index.</p>}
      {search.data.results.map(result => <article key={result.citation_id} className="space-y-2 rounded-lg border border-stroke bg-white p-3">
        <p className="text-xs font-semibold">{result.filename} · chunk {result.chunk_index + 1} · characters {result.start}–{result.end}</p>
        <blockquote dir="auto" className="whitespace-pre-wrap border-l-2 border-primary pl-3 text-sm">{result.quote}</blockquote>
        <a className="text-xs font-semibold text-primary" href={`/api/bridge/policies/${encodeURIComponent(result.policy_id)}/original`}>Open original policy</a>
        <p className="text-xs text-muted">Quotation matched to the current source. Rule approval is separate.</p>
      </article>)}
    </div>}
  </section>;
}
