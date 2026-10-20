"use client";

import { useCallback, useRef, useState } from "react";
import Link from "next/link";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { AlertCircle, ArrowRight, CheckCircle2, CloudUpload, FileCheck2, FileText, Info, LoaderCircle, Sparkles, X } from "lucide-react";
import { api, ApiError } from "@/lib/api";
import { formatSize } from "@/lib/utils";
import { Button } from "@/components/ui/button";
import { Card, CardHeader, CardTitle } from "@/components/ui/card";
import { SectionHeading } from "@/components/feedback";

const allowed = new Set(["pdf", "docx", "pptx", "png", "jpg", "jpeg"]);
const MAX = 20 * 1024 * 1024;

export default function UploadPage() {
  const fileRef = useRef<HTMLInputElement>(null);
  const qc = useQueryClient();
  const [file, setFile] = useState<File | null>(null);
  const [isDragging, setDragging] = useState(false);
  const [error, setError] = useState("");
  const upload = useMutation({ mutationFn: api.upload, onSuccess: () => { qc.invalidateQueries({ queryKey: ["documents"] }); qc.invalidateQueries({ queryKey: ["pending-reviews"] }); } });

  const selectFile = useCallback((candidate: File | null) => {
    upload.reset(); setError("");
    if (!candidate) return;
    const extension = candidate.name.split(".").pop()?.toLowerCase() || "";
    if (!allowed.has(extension)) { setError("Unsupported format. Choose PDF, DOCX, PPTX, PNG, JPG or JPEG."); setFile(null); return; }
    if (candidate.size > MAX) { setError("File exceeds the 20 MB frontend limit."); setFile(null); return; }
    setFile(candidate);
  }, [upload]);

  const duplicateId = (() => {
    const detail = upload.error instanceof ApiError ? (upload.error.details as { detail?: { existing_document_id?: string } } | null)?.detail : undefined;
    return typeof detail === "object" && detail?.existing_document_id ? detail.existing_document_id : null;
  })();

  return <>
    <SectionHeading eyebrow="AI ingestion" title="Upload a document" description="Your file goes to FastAPI for text extraction, classification, and Gemini-powered structured extraction. Results remain subject to review."/>
    <div className="grid gap-6 xl:grid-cols-[1.65fr_1fr]">
      <div className="space-y-6">
        <Card className="overflow-hidden"><CardHeader><div><CardTitle>Document intake</CardTitle><p className="mt-1 text-[12px] text-muted">Select one file to process securely through your local backend.</p></div><div className="rounded-xl bg-[#f0efff] p-2.5 text-primary"><CloudUpload size={21}/></div></CardHeader>
          <div className="px-6 pb-6"><input ref={fileRef} type="file" accept=".pdf,.docx,.pptx,.png,.jpg,.jpeg" className="sr-only" aria-label="Choose document" onChange={(e) => selectFile(e.target.files?.[0] || null)} />
            <div role="button" tabIndex={0} aria-label="Choose a document to upload" onKeyDown={(e) => { if (e.key === "Enter" || e.key === " ") { e.preventDefault(); fileRef.current?.click(); } }} onClick={() => fileRef.current?.click()} onDragOver={(e) => { e.preventDefault(); setDragging(true); }} onDragLeave={() => setDragging(false)} onDrop={(e) => { e.preventDefault(); setDragging(false); selectFile(e.dataTransfer.files[0] || null); }} className={`flex min-h-[270px] cursor-pointer flex-col items-center justify-center rounded-[18px] border-2 border-dashed px-6 text-center transition-all ${isDragging ? "border-primary bg-[#f0efff]" : "border-[#d9dded] bg-[#fafbff] hover:border-[#a6a0f9] hover:bg-[#f8f7ff]"}`}>
              <div className="mb-5 flex h-16 w-16 items-center justify-center rounded-[20px] bg-[#eeedff] text-primary"><CloudUpload size={28} strokeWidth={1.7}/></div><h2 className="text-base font-semibold text-ink">Drag & drop your document here</h2><p className="mt-2 text-[13px] text-muted">or <span className="font-semibold text-primary">browse files</span> from your computer</p><div className="mt-6 rounded-lg border border-stroke bg-white px-3 py-2 text-[11px] font-medium text-muted">PDF · DOCX · PPTX · PNG · JPG · JPEG</div>
            </div>
            {file && <div className="mt-4 flex items-center gap-3 rounded-2xl border border-[#dcefe8] bg-[#f7fffb] p-4"><div className="rounded-xl bg-[#e5f7ef] p-3 text-[#259868]"><FileCheck2 size={21}/></div><div className="min-w-0 flex-1"><div className="truncate text-sm font-semibold text-ink">{file.name}</div><div className="mt-1 text-[11px] text-muted">{formatSize(file.size)} · Ready to process</div></div><button aria-label="Remove selected file" className="rounded-lg p-2 text-muted hover:bg-white" onClick={() => { setFile(null); if (fileRef.current) fileRef.current.value = ""; }}><X size={17}/></button></div>}
            {error && <div role="alert" className="mt-4 flex items-start gap-2 rounded-xl bg-[#fff2f2] p-3 text-[12px] text-[#bb4254]"><AlertCircle size={16} className="shrink-0"/>{error}</div>}
            {upload.isError && <div role="alert" className="mt-4 rounded-xl border border-[#ffdfe5] bg-[#fff5f6] p-4 text-[12px] text-[#b43b52]"><p>{upload.error.message}</p>{duplicateId && <Link href={`/documents/${duplicateId}`} className="mt-2 inline-block font-semibold underline">Open existing document →</Link>}</div>}
            {upload.isSuccess ? <div className="mt-5 flex flex-wrap items-center justify-between gap-3 rounded-xl border border-[#c2eddb] bg-[#f1fcf6] p-4"><div className="flex items-center gap-2 text-[13px] font-semibold text-[#25865b]"><CheckCircle2 size={19}/>Document processed successfully</div><Button asChild><Link href={`/documents/${upload.data.document_id}`}>View results <ArrowRight size={16}/></Link></Button></div> : <Button size="lg" className="mt-5 w-full" disabled={!file || upload.isPending} onClick={() => file && upload.mutate(file)}>{upload.isPending ? <><LoaderCircle className="animate-spin" size={18}/>Analyzing document… this may take a minute</> : <><Sparkles size={18}/>Upload & analyze document</>}</Button>}
            <p className="mt-3 text-center text-[11px] text-[#9ca5b5]">The uploaded file is stored by FastAPI, not in your browser. Maximum frontend upload: 20 MB.</p>
          </div></Card>
      </div>
      <div className="space-y-5"><Card className="p-6"><div className="flex items-center gap-2 text-primary"><Sparkles size={19}/><h3 className="text-[14px] font-semibold text-ink">What happens next?</h3></div><div className="mt-6 space-y-6">{[
        { num: "01", title: "Text extraction", desc: "Reads content using parsers and OCR where supported." },
        { num: "02", title: "Document classification", desc: "Determines whether this is a receipt, invoice, CV or contract." },
        { num: "03", title: "AI structured extraction", desc: "Gemini identifies fields; rule-based extraction can act as fallback." },
        { num: "04", title: "Human oversight", desc: "Low-confidence results are flagged for review." },
      ].map(({ num, title, desc }) => <div key={num} className="flex gap-4"><div className="flex h-9 w-9 shrink-0 items-center justify-center rounded-xl bg-[#f0efff] text-[11px] font-bold text-primary">{num}</div><div><div className="text-[13px] font-semibold text-ink">{title}</div><p className="mt-1 text-[12px] leading-relaxed text-muted">{desc}</p></div></div>)}</div></Card>
        <div className="flex items-start gap-3 rounded-[18px] border border-[#dfebff] bg-[#f4f8ff] p-5"><Info className="mt-0.5 shrink-0 text-[#5b83d6]" size={18}/><div><div className="text-[12px] font-semibold text-[#3b64a3]">Development environment</div><p className="mt-2 text-[12px] leading-relaxed text-[#6680a7]">No production authentication or organization isolation is active yet. Use synthetic documents, not confidential company files.</p></div></div>
      </div>
    </div>
  </>;
}
