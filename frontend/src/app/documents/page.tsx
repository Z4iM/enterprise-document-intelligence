"use client";

import { useMemo, useState } from "react";
import Link from "next/link";
import { useQuery } from "@tanstack/react-query";
import { FilePlus2, Search, SlidersHorizontal } from "lucide-react";
import { api } from "@/lib/api";
import { DocumentsTable } from "@/components/documents-table";
import { EmptyState, ErrorState, LoadingState, SectionHeading } from "@/components/feedback";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";

export default function DocumentsPage() {
  const docs = useQuery({ queryKey: ["documents"], queryFn: api.documents });
  const [search, setSearch] = useState("");
  const [status, setStatus] = useState("all");
  const filtered = useMemo(() => (docs.data || []).filter((d) => {
    const matchText = [d.filename, d.document_type, d.document_id].some((v) => v?.toLowerCase().includes(search.toLowerCase()));
    return matchText && (status === "all" || d.review_status === status);
  }), [docs.data, search, status]);
  return <>
    <SectionHeading eyebrow="Document workspace" title="Your documents" description="Browse, search and inspect the files processed by your document intelligence API." action={<Button asChild><Link href="/upload"><FilePlus2 size={17}/> New document</Link></Button>}/>
    <div className="mb-5 flex flex-col items-stretch justify-between gap-4 rounded-2xl border border-stroke bg-white p-4 sm:flex-row sm:items-center"><div className="relative w-full sm:max-w-[360px]"><Search size={17} className="absolute left-3.5 top-3.5 text-[#9ca5b7]"/><Input className="pl-10" placeholder="Search filename, ID or category..." value={search} onChange={(e) => setSearch(e.target.value)}/></div><label className="flex items-center gap-2 text-[#8690a4]"><SlidersHorizontal size={17}/><span className="sr-only">Filter by review status</span><select className="h-10 rounded-xl border border-stroke bg-white px-3 text-[12px] font-semibold text-ink outline-none" value={status} onChange={(e) => setStatus(e.target.value)}><option value="all">All review statuses</option><option value="needs_review">Needs review</option><option value="approved">Approved</option><option value="corrected">Corrected</option><option value="rejected">Rejected</option></select></label></div>
    {docs.isLoading ? <LoadingState/> : docs.isError ? <ErrorState error={docs.error} retry={() => docs.refetch()}/> : <>
      <div className="mb-4 text-[12px] font-medium text-muted">Showing {filtered.length} of {docs.data?.length ?? 0} documents</div>
      {filtered.length ? <DocumentsTable documents={filtered}/> : <EmptyState title="No matching documents" description={docs.data?.length ? "Try a different search or review-status filter." : "Upload a file to populate your document workspace."} action={<Button asChild variant="secondary"><Link href="/upload">Upload document</Link></Button>}/>}
    </>}
  </>;
}
