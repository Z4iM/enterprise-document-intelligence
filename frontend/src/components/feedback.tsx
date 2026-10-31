import { AlertCircle, Inbox, LoaderCircle, WifiOff } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { ApiError } from "@/lib/api";

export function SectionHeading({ eyebrow, title, description, action }: { eyebrow?: string; title: string; description?: string; action?: React.ReactNode }) {
  return <div className="mb-8 flex flex-wrap items-start justify-between gap-4"><div>{eyebrow && <div className="mb-2 text-[11px] font-bold uppercase tracking-[.2em] text-primary">{eyebrow}</div>}<h1 className="text-[28px] font-bold tracking-[-.05em] text-ink md:text-[32px]">{title}</h1>{description && <p className="mt-2 max-w-2xl text-[13px] leading-relaxed text-muted">{description}</p>}</div>{action}</div>;
}

export function LoadingState({ label = "Loading workspace data..." }: { label?: string }) {
  return <Card className="flex min-h-52 flex-col items-center justify-center gap-3 p-8 text-muted"><LoaderCircle size={26} className="animate-spin text-primary"/><p className="text-sm">{label}</p></Card>;
}

export function ErrorState({ error, retry }: { error: unknown; retry?: () => void }) {
  const message = error instanceof Error ? error.message : "Something went wrong.";
  const offline = error instanceof ApiError && error.status === 502;
  return <Card className="flex flex-col items-center justify-center p-9 text-center"><div className="mb-4 rounded-2xl bg-[#fff1f0] p-4 text-[#cd5362]">{offline ? <WifiOff size={23} /> : <AlertCircle size={23} />}</div><div className="font-semibold text-ink">{offline ? "FastAPI is not responding" : "Unable to load data"}</div><p className="mt-2 max-w-lg text-sm leading-relaxed text-muted">{message}</p>{error instanceof ApiError && error.requestId && <p className="mt-2 break-all font-mono text-xs text-muted">Request reference: {error.requestId}</p>}{retry && <Button variant="secondary" className="mt-5" onClick={retry}>Try again</Button>}</Card>;
}

export function EmptyState({ title, description, action }: { title: string; description: string; action?: React.ReactNode }) {
  return <Card className="flex flex-col items-center justify-center px-6 py-16 text-center"><div className="mb-4 rounded-2xl bg-[#f1f0ff] p-4 text-primary"><Inbox size={24}/></div><h3 className="font-semibold text-ink">{title}</h3><p className="mt-2 max-w-sm text-[13px] leading-relaxed text-muted">{description}</p>{action && <div className="mt-5">{action}</div>}</Card>;
}

export function Field({ label, children }: { label: string; children: React.ReactNode }) {
  return <label className="block"><span className="mb-2 block text-[12px] font-semibold text-[#424e66]">{label}</span>{children}</label>;
}
