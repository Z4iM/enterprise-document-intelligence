import { cn } from "@/lib/utils";

const colors: Record<string, string> = {
  completed: "border-[#bdeedb] bg-[#e7f8f0] text-[#16794d]",
  approved: "border-[#bdeedb] bg-[#e7f8f0] text-[#16794d]",
  passed: "border-[#bdeedb] bg-[#e7f8f0] text-[#16794d]",
  healthy: "border-[#bdeedb] bg-[#e7f8f0] text-[#16794d]",
  verified: "border-[#bdeedb] bg-[#e7f8f0] text-[#16794d]",
  needs_review: "border-[#ffebc1] bg-[#fff7e2] text-[#9b6911]",
  processing: "border-[#c5deff] bg-[#edf5ff] text-[#3576ca]",
  pending: "border-[#ffebc1] bg-[#fff7e2] text-[#9b6911]",
  requires_approval: "border-[#ffebc1] bg-[#fff7e2] text-[#9b6911]",
  corrected: "border-[#ddd2ff] bg-[#f2edff] text-[#7753c4]",
  failed: "border-[#ffd8df] bg-[#fff0f3] text-[#c33d52]",
  rejected: "border-[#ffd8df] bg-[#fff0f3] text-[#c33d52]",
  violation: "border-[#ffd8df] bg-[#fff0f3] text-[#c33d52]",
};

export function StatusBadge({ status, className }: { status: string | null | undefined; className?: string }) {
  const value = (status || "unknown").toLowerCase();
  const label = value.replace(/_/g, " ");
  return <span className={cn("inline-flex items-center gap-1.5 rounded-full border px-2.5 py-1 text-[11px] font-bold capitalize tracking-[.01em]", colors[value] || "border-stroke bg-[#f5f7fa] text-muted", className)}><span className="h-1.5 w-1.5 rounded-full bg-current opacity-75" />{label}</span>;
}
