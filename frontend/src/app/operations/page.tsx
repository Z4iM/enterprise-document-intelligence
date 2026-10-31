"use client";

import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { useAuth } from "@/components/auth";
import { Card } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import {
  ErrorState,
  LoadingState,
  SectionHeading,
} from "@/components/feedback";
import { request } from "@/lib/api";

type Span = {
  trace_id: string;
  span_id: string;
  parent_span_id: string | null;
  operation: string;
  status: string;
  duration_ms: number;
  created_at: string;
  measurements: Record<string, number>;
};
type Summary = {
  enabled: boolean;
  window_hours: number;
  sample_limit: number;
  sample_count: number;
  truncated: boolean;
  best_effort: boolean;
  storage_rows: number;
  storage_cap_per_organization: number;
  queue: Record<string, number>;
  expired_leases: number;
  oldest_ready_wait_seconds: number | null;
  operations: {
    operation: string;
    count: number;
    errors: number;
    p50_ms: number;
    p95_ms: number;
  }[];
  llm: {
    calls: number;
    usage_reported_calls: number;
    priced_calls: number;
    reported_prompt_tokens: number | null;
    reported_output_tokens: number | null;
    reported_total_tokens: number | null;
    estimated_usd_known_calls: number | null;
    cost_complete: boolean;
  };
  alerts: string[];
  recent_spans: Span[];
};
const known = (value: number | null | undefined) =>
  value == null ? "Unknown" : value.toLocaleString();

export default function Operations() {
  const { user } = useAuth();
  const [selected, setSelected] = useState("");
  const [reference, setReference] = useState("");
  const allowed = user?.role === "admin";
  const summary = useQuery({
    queryKey: ["operations"],
    queryFn: () => request<Summary>("/operations/summary"),
    enabled: allowed,
    refetchInterval: allowed ? 10000 : false,
  });
  const trace = useQuery({
    queryKey: ["operations-trace", selected],
    queryFn: () =>
      request<{ trace_id: string; spans: Span[]; truncated: boolean }>(
        `/operations/traces/${selected}`,
      ),
    enabled: allowed && /^[a-f0-9]{32}$/.test(selected),
  });
  if (!allowed)
    return (
      <Card className="p-6">Operations requires an administrator account.</Card>
    );
  if (summary.isPending)
    return <LoadingState label="Loading organization operations…" />;
  if (summary.isError)
    return <ErrorState error={summary.error} retry={() => summary.refetch()} />;
  const data = summary.data;
  return (
    <>
      <SectionHeading
        eyebrow="Operational evidence"
        title="Operations"
        description="Queue health and content-free traces for your organization. Telemetry is best effort and never changes policy outcomes."
      />
      <p className="mb-5 text-sm text-muted">
        Latest {data.sample_count} spans from {data.window_hours} hours, capped
        at {data.sample_limit}
        {data.truncated ? " · sample truncated" : ""}. Timings describe this
        sample, not a load-test SLO. Recording{" "}
        {data.enabled ? "enabled" : "disabled"}.
      </p>
      <div className="mb-6 grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
        <Card className="p-5">
          <h2 className="text-sm font-semibold">Queue</h2>
          <p className="mt-2 text-2xl font-bold">
            {(data.queue.queued || 0) + (data.queue.retry_wait || 0)} waiting
          </p>
          <p className="mt-2 text-xs text-muted">
            {data.queue.running || 0} running · {data.queue.failed || 0} failed
            · {data.queue.completed || 0} completed
          </p>
        </Card>
        <Card className="p-5">
          <h2 className="text-sm font-semibold">Model requests</h2>
          <p className="mt-2 text-2xl font-bold">{data.llm.calls}</p>
          <p className="mt-2 text-xs text-muted">
            Usage reported for {data.llm.usage_reported_calls} calls. Missing
            usage stays unknown.
          </p>
        </Card>
        <Card className="p-5">
          <h2 className="text-sm font-semibold">Reported tokens</h2>
          <p className="mt-2 text-2xl font-bold">
            {known(data.llm.reported_total_tokens)}
          </p>
          <p className="mt-2 text-xs text-muted">
            Prompt {known(data.llm.reported_prompt_tokens)} · response{" "}
            {known(data.llm.reported_output_tokens)}
          </p>
        </Card>
        <Card className="p-5">
          <h2 className="text-sm font-semibold">Configured cost estimate</h2>
          <p className="mt-2 text-2xl font-bold">
            {data.llm.estimated_usd_known_calls == null
              ? "Unknown"
              : `$${data.llm.estimated_usd_known_calls.toFixed(6)}`}
          </p>
          <p className="mt-2 text-xs text-muted">
            {data.llm.priced_calls}/{data.llm.calls} calls priced ·{" "}
            {data.llm.cost_complete ? "sample covered" : "incomplete coverage"}.
            Estimate, not an invoice.
          </p>
        </Card>
      </div>
      {data.alerts.length > 0 && (
        <Card className="mb-6 border-amber-300 p-5">
          <h2 className="font-semibold">Attention needed</h2>
          <ul className="mt-2 list-inside list-disc text-sm">
            {data.alerts.map((alert) => (
              <li key={alert}>{alert}</li>
            ))}
          </ul>
        </Card>
      )}
      <div className="grid gap-6 xl:grid-cols-2">
        <Card className="overflow-x-auto p-5">
          <h2 className="mb-4 font-semibold">Latency and errors</h2>
          {!data.operations.length ? (
            <p className="text-sm text-muted">
              No recorded operations yet. Complete an authenticated document or
              workflow action.
            </p>
          ) : (
            <table aria-label="Operation latency and errors" className="w-full min-w-[580px] text-left text-xs [&_th]:whitespace-nowrap [&_th]:px-3 [&_th]:py-2 [&_td]:px-3 [&_td]:py-2">
              <thead>
                <tr>
                  <th className="p-2">Operation</th>
                  <th>Count</th>
                  <th>Errors</th>
                  <th>P50 ms</th>
                  <th>P95 ms</th>
                </tr>
              </thead>
              <tbody>
                {data.operations.map((row) => (
                  <tr className="border-t" key={row.operation}>
                    <td className="p-2">{row.operation}</td>
                    <td>{row.count}</td>
                    <td>{row.errors}</td>
                    <td>{row.p50_ms}</td>
                    <td>{row.p95_ms}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </Card>
        <Card className="space-y-3 p-5">
          <h2 className="font-semibold">Recovery and storage</h2>
          <p className="text-sm">
            Expired leases: {data.expired_leases}. Oldest ready job wait:{" "}
            {known(data.oldest_ready_wait_seconds)} seconds.
          </p>
          <p className="text-sm text-muted">
            {data.storage_rows.toLocaleString()} /{" "}
            {data.storage_cap_per_organization.toLocaleString()} stored spans.
            Recording stops at the soft cap; history is not deleted
            automatically. Backups and authorized retention remain operator
            responsibilities.
          </p>
          <form
            className="space-y-2"
            onSubmit={(event) => {
              event.preventDefault();
              setSelected(reference);
            }}
          >
            <label className="block text-sm">
              Find request trace
              <input
                aria-label="Trace reference"
                className="mt-1 w-full rounded border p-2 font-mono text-xs"
                value={reference}
                maxLength={32}
                pattern="[a-f0-9]{32}"
                onChange={(event) => setReference(event.target.value)}
              />
            </label>
            <Button size="sm" disabled={!/^[a-f0-9]{32}$/.test(reference)}>
              Find trace
            </Button>
          </form>
        </Card>
      </div>
      <Card className="mt-6 p-5">
        <h2 className="mb-3 font-semibold">Recent spans</h2>
        <div className="grid gap-2 md:grid-cols-2">
          {data.recent_spans.slice(0, 12).map((row) => (
            <button
              key={row.span_id}
              className="rounded border p-3 text-left text-xs"
              onClick={() => {
                setSelected(row.trace_id);
                setReference(row.trace_id);
              }}
            >
              <span className="font-semibold">{row.operation}</span> ·{" "}
              {row.status} · {row.duration_ms} ms
              <span className="mt-1 block break-all font-mono text-muted">
                {row.trace_id}
              </span>
            </button>
          ))}
        </div>
      </Card>
      {selected && (
        <Card className="mt-6 space-y-3 p-5">
          <h2 className="font-semibold">Trace details</h2>
          <p className="break-all font-mono text-xs">{selected}</p>
          {trace.isPending ? (
            <p>Loading trace…</p>
          ) : trace.isError ? (
            <ErrorState error={trace.error} />
          ) : (
            <>
              <p className="text-xs text-muted">
                Parent links join request, job, stage, tool and model spans.
                Retries can create several attempts; incomplete traces do not
                prove completion.
              </p>
              {trace.data?.spans.map((row) => (
                <div
                  key={row.span_id}
                  className="space-y-1 rounded border p-3 text-xs"
                >
                  <p className="font-semibold">
                    {row.operation} · {row.status} · {row.duration_ms} ms
                  </p>
                  <p className="break-all font-mono text-muted">
                    Span {row.span_id} · parent {row.parent_span_id || "root"}
                  </p>
                  {Object.entries(row.measurements).map(([key, value]) => (
                    <span key={key} className="mr-3 inline-block">
                      {key.replaceAll("_", " ")}: {value}
                    </span>
                  ))}
                </div>
              ))}
              {trace.data?.truncated && (
                <p>Showing the first 128 recorded spans.</p>
              )}
            </>
          )}
        </Card>
      )}
    </>
  );
}
