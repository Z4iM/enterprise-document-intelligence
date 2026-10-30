"use client";

import { useEffect } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { request } from "@/lib/api";
import { Button } from "@/components/ui/button";
import { useAuth } from "@/components/auth";

type JobStatus = {state: string; attempts: number; max_attempts?: number; error: string | null};

export function ProcessingStatus({kind, id}: {kind: "documents" | "policies"; id: string}) {
  const {user} = useAuth();
  const cache = useQueryClient();
  const status = useQuery({queryKey: ["processing", kind, id], queryFn: () => request<JobStatus>(`/${kind}/${encodeURIComponent(id)}/processing`),
    enabled: !!id, refetchInterval: query => ["queued", "running", "retry_wait", "processing"].includes(query.state.data?.state || "") ? 1500 : false});
  const retry = useMutation({mutationFn: () => request(`/${kind}/${encodeURIComponent(id)}/processing/retry`, {method: "POST"}), onSuccess: () => {cache.invalidateQueries({queryKey: ["processing", kind, id]});}});
  const state = status.data?.state;
  useEffect(() => {
    if (state === "completed" || state === "failed") {
      cache.invalidateQueries({queryKey: ["document", id]});
      cache.invalidateQueries({queryKey: ["policy-rules", id]});
      cache.invalidateQueries({queryKey: ["documents"]});
    }
  }, [state, cache, id]);
  if (status.isError) return <p role="alert" className="text-sm text-red-700">Could not load processing status.</p>;
  if (!state || ["completed", "not_started", "completed_with_rejections"].includes(state)) return null;
  return <div role="status" className="space-y-2 rounded-xl border border-stroke bg-white p-4 text-sm">
    <p className="font-semibold">{state === "failed" ? "Processing needs attention" : state === "retry_wait" ? "Processing will retry automatically" : "Processing your file…"}</p>
    <p className="text-xs text-muted">{state} · attempt {status.data?.attempts || 0}{status.data?.max_attempts ? ` of ${status.data.max_attempts}` : ""}. Your original file is saved.</p>
    {status.data?.error && <p className="text-xs text-muted">{status.data.error}</p>}
    {state === "failed" && (kind === "documents" || user?.role === "reviewer" || user?.role === "admin") && <Button size="sm" disabled={retry.isPending} onClick={() => retry.mutate()}>Retry processing</Button>}
    {retry.isError && <p role="alert" className="text-xs text-red-700">{retry.error.message}</p>}
  </div>;
}
