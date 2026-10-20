import Link from "next/link";
import { ArrowUpRight, FileImage, FileText, FileType2, FileUser, ReceiptText } from "lucide-react";
import type { DocumentSummary } from "@/lib/types";
import { StatusBadge } from "@/components/ui/badge";
import { Card } from "@/components/ui/card";
import { formatDate, labelize, shortId } from "@/lib/utils";

function TypeIcon({ kind }: { kind: string | null }) {
  const icon = kind === "receipt" ? ReceiptText : kind === "cv" ? FileUser : kind === "invoice" ? FileType2 : kind === "image" ? FileImage : FileText;
  const Icon = icon;
  return <span className="flex h-10 w-10 shrink-0 items-center justify-center rounded-xl border border-[#e8e7fe] bg-[#f4f3ff] text-[#6761cf]"><Icon size={19}/></span>;
}

export function DocumentsTable({ documents, compact = false }: { documents: DocumentSummary[]; compact?: boolean }) {
  return <Card className="overflow-hidden"><div className="overflow-x-auto smooth-scrollbar"><table className="interactive-table min-w-[760px]"><thead><tr><th>Document</th><th>Classification</th><th>Processing</th><th>Review</th><th>Uploaded</th><th aria-label="Open"/></tr></thead><tbody>{documents.slice(0, compact ? 6 : undefined).map((doc) => <tr key={doc.document_id}>
    <td><Link href={`/documents/${doc.document_id}`} className="group flex items-center gap-3"><TypeIcon kind={doc.document_type}/><div className="min-w-0"><div className="max-w-[250px] truncate font-semibold text-ink group-hover:text-primary" title={doc.filename}>{doc.filename}</div><div className="mt-1 font-mono text-[10px] tracking-tight text-[#9aa3b5]">{shortId(doc.document_id)}</div></div></Link></td>
    <td><span className="font-medium text-ink">{labelize(doc.document_type)}</span>{doc.classification_confidence != null && <div className="mt-1 text-[11px] text-[#929cb0]">{Math.round(doc.classification_confidence * 100)}% confidence</div>}</td>
    <td><StatusBadge status={doc.processing_status}/></td><td><StatusBadge status={doc.review_status}/></td><td className="whitespace-nowrap text-muted">{formatDate(doc.created_at)}</td><td><Link aria-label={`View ${doc.filename}`} href={`/documents/${doc.document_id}`} className="inline-flex rounded-lg p-2 text-[#8d96a9] hover:bg-[#f0f0ff] hover:text-primary"><ArrowUpRight size={17}/></Link></td>
  </tr>)}</tbody></table></div></Card>;
}
