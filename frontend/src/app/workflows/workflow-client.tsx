"use client";

import { useRef, useState } from "react";
import Link from "next/link";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { api, ApiError, csrfHeaders } from "@/lib/api";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { SectionHeading } from "@/components/feedback";
import { DocumentationChecklist } from "@/components/documentation-checklist";
import { useAuth } from "@/components/auth";

type Agent = {
  role: string;
  mode: string;
  decision: string;
  calls: number;
  latency_ms: number;
  tools: { tool: string; status: string }[];
};
type Run = {
  workflow_id: string;
  document_id: string;
  policy_id: string;
  question: string;
  status: string;
  error: string | null;
  resumes: number;
  result: {
    reason?: string;
    model_calls?: number;
    document_agent?: Agent;
    policy_agent?: Agent;
    trace?: { node: string; status: string }[];
    evaluation?: {
      status?: string;
      coverage?: string;
      evaluation?: {
        required_actions: {
          rule_id: string;
          action: string;
          explanation: string;
        }[];
      };
      evidence?: { rule_id: string; source_quote: string }[];
    };
  };
};

async function workflowRequest<T>(path: string, payload?: object): Promise<T> {
  const headers: Record<string, string> = {};
  if (payload)
    Object.assign(headers, await csrfHeaders(), {
      "Content-Type": "application/json",
    });
  const response = await fetch(`/api/workflows/runs${path}`, {
    method: payload ? "POST" : "GET",
    headers,
    body: payload ? JSON.stringify(payload) : undefined,
    cache: "no-store",
  });
  const body = await response.json();
  if (!response.ok)
    throw new ApiError(
      body.detail || "Workflow request failed.",
      response.status,
      body,
      response.headers.get("x-request-id"),
    );
  return body as T;
}

export default function WorkflowClient({ available }: { available: boolean }) {
  const { user } = useAuth();
  const staff = user?.role === "reviewer" || user?.role === "admin";
  const cache = useQueryClient();
  const [documentId, setDocument] = useState("");
  const [policyId, setPolicy] = useState("");
  const [question, setQuestion] = useState("");
  const [selected, setSelected] = useState("");
  const request = useRef({ fingerprint: "", key: "" });
  const documents = useQuery({
    queryKey: ["documents"],
    queryFn: api.documents,
    enabled: available,
  });
  const policies = useQuery({
    queryKey: ["policies"],
    queryFn: api.policies,
    enabled: available,
  });
  const runs = useQuery({
    queryKey: ["specialist-runs"],
    queryFn: () => workflowRequest<Run[]>(""),
    enabled: available,
    refetchInterval: available ? 2000 : false,
  });
  const detail = useQuery({
    queryKey: ["specialist-run", selected],
    queryFn: () => workflowRequest<Run>(`/${selected}`),
    enabled: available && !!selected,
    refetchInterval: available && selected ? 2000 : false,
  });
  const current = detail.data;
  const start = useMutation({
    mutationFn: () => {
      const fingerprint = JSON.stringify([
        documentId,
        policyId,
        question.trim(),
      ]);
      if (request.current.fingerprint !== fingerprint)
        request.current = { fingerprint, key: crypto.randomUUID() };
      return workflowRequest<Run>("", {
        document_id: documentId,
        policy_id: policyId,
        question: question.trim(),
        request_key: request.current.key,
      });
    },
    onSuccess: (run) => {
      setSelected(run.workflow_id);
      cache.invalidateQueries({ queryKey: ["specialist-runs"] });
    },
  });
  const resume = useMutation({
    mutationFn: () => workflowRequest<Run>(`/${selected}/resume`, {}),
    onSuccess: () => cache.invalidateQueries({ queryKey: ["specialist-runs"] }),
  });
  return (
    <>
      <SectionHeading
        eyebrow="Bounded specialist coordination"
        title="Workflow orchestration"
        description="Document analysis and policy research have separate tools. A deterministic evaluator checks reviewed fields against all verified approved rules."
      />
      {!available ? (
        <Card className="space-y-3 p-6">
          <h2 className="font-semibold">Local workflow controls unavailable</h2>
          <p>
            Workflows require explicitly enabled local development and a private
            server token. Production builds keep the gateway disabled.
          </p>
          <Link className="text-primary" href="/documents">
            Open documents
          </Link>
        </Card>
      ) : (
        <div className="grid gap-6 lg:grid-cols-[.8fr_1.2fr]">
          <div className="space-y-4">
            <Card className="space-y-4 p-5">
              <h2 className="font-semibold">Start an investigation workflow</h2>
              <label className="block text-sm">
                Document
                <select
                  aria-label="Workflow document"
                  className="mt-1 block w-full rounded border p-2"
                  value={documentId}
                  onChange={(e) => setDocument(e.target.value)}
                >
                  <option value="">Select your document</option>
                  {documents.data?.map((doc) => (
                    <option key={doc.document_id} value={doc.document_id}>
                      {doc.filename}
                    </option>
                  ))}
                </select>
              </label>
              <label className="block text-sm">
                Policy
                <select
                  aria-label="Workflow policy"
                  className="mt-1 block w-full rounded border p-2"
                  value={policyId}
                  onChange={(e) => setPolicy(e.target.value)}
                >
                  <option value="">Select organization policy</option>
                  {policies.data?.map((policy) => (
                    <option key={policy.policy_id} value={policy.policy_id}>
                      {policy.filename}
                    </option>
                  ))}
                </select>
              </label>
              <label className="block text-sm">
                Question
                <textarea
                  aria-label="Workflow question"
                  dir="auto"
                  maxLength={1500}
                  value={question}
                  onChange={(e) => setQuestion(e.target.value)}
                  className="mt-1 w-full rounded border p-2"
                />
              </label>
              <p className="text-xs text-muted">
                Uses configured Gemini specialists when available; otherwise
                clearly labeled deterministic fallback. Nothing approves an
                expense.
              </p>
              <Button
                disabled={
                  !documentId ||
                  !policyId ||
                  !question.trim() ||
                  start.isPending
                }
                onClick={() => start.mutate()}
              >
                Start workflow
              </Button>
            </Card>
            <Card className="space-y-2 p-5">
              <h2 className="font-semibold">Recent authorized workflows</h2>
              {runs.data?.map((run) => (
                <button
                  key={run.workflow_id}
                  className="block w-full rounded border p-3 text-left text-sm"
                  onClick={() => setSelected(run.workflow_id)}
                >
                  {run.question}
                  <span className="mt-1 block text-xs text-muted">
                    {run.status.replaceAll("_", " ")}
                  </span>
                </button>
              ))}
            </Card>
          </div>
          <div className="space-y-4">
            {current ? (
              <Card className="space-y-4 p-5">
                <h2 className="font-semibold">Workflow status</h2>
                <p role="status">{current.status.replaceAll("_", " ")}</p>
                <p className="text-sm text-muted">{current.result.reason}</p>
                {current.error && <p role="alert">{current.error}</p>}
                {[current.result.document_agent, current.result.policy_agent]
                  .filter(Boolean)
                  .map((agent) => (
                    <section
                      className="rounded border p-3 text-sm"
                      key={agent!.role}
                    >
                      <h3 className="font-semibold">
                        {agent!.role} specialist
                      </h3>
                      <p>
                        {agent!.mode.replaceAll("_", " ")} · advisory{" "}
                        {agent!.decision} · {agent!.calls} model calls
                      </p>
                      <p className="text-xs text-muted">
                        {agent!.tools
                          .map((tool) => `${tool.tool}: ${tool.status}`)
                          .join(" · ")}
                      </p>
                    </section>
                  ))}
                <ol className="space-y-1 text-xs">
                  {current.result.trace?.map((event, index) => (
                    <li key={index}>
                      {index + 1}. {event.node.replaceAll("_", " ")} →{" "}
                      {event.status.replaceAll("_", " ")}
                    </li>
                  ))}
                </ol>
                {current.result.evaluation?.status && (
                  <div className="space-y-2">
                    <h3 className="font-semibold">
                      Approved-rule outcome:{" "}
                      {current.result.evaluation.status.replaceAll("_", " ")}
                    </h3>
                    {current.result.evaluation.evaluation?.required_actions.map(
                      (action) => (
                        <p key={action.rule_id} className="text-sm">
                          {action.explanation}
                        </p>
                      ),
                    )}
                    {current.result.evaluation.evidence?.map((evidence) => (
                      <blockquote
                        key={evidence.rule_id}
                        dir="auto"
                        className="border-l-2 border-primary pl-3 text-sm"
                      >
                        {evidence.source_quote}
                      </blockquote>
                    ))}
                    <p className="text-xs text-muted">
                      Approved rules only. Completed investigation does not mean
                      approved reimbursement.
                    </p>
                  </div>
                )}
                {current.status.startsWith("waiting_") ||
                current.status === "needs_revalidation" ||
                current.status === "failed" ||
                current.status === "blocked" ? (
                  <>
                    <div className="flex gap-3 text-sm">
                      {staff ? (
                        <Link
                          href={`/reviews?document=${current.document_id}`}
                          className="text-primary"
                        >
                          Review document
                        </Link>
                      ) : (
                        <span>
                          Ask a reviewer to verify your fields and evidence.
                        </span>
                      )}
                      <Link href="/policies" className="text-primary">
                        {staff ? "Review policy rules" : "View policy"}
                      </Link>
                    </div>
                    <Button
                      disabled={resume.isPending || current.resumes >= 8}
                      onClick={() => resume.mutate()}
                    >
                      Recheck recorded reviews and resume
                    </Button>
                  </>
                ) : null}
              </Card>
            ) : (
              <Card className="p-5">
                Choose a workflow to inspect its checkpoints and trace.
              </Card>
            )}
            {current && (
              <DocumentationChecklist
                documentId={current.document_id}
                policyId={current.policy_id}
              />
            )}
          </div>
        </div>
      )}
      {(start.isError ||
        resume.isError ||
        runs.isError ||
        documents.isError ||
        policies.isError) && (
        <p role="alert" className="mt-4 text-red-700">
          {start.error?.message ||
            resume.error?.message ||
            runs.error?.message ||
            documents.error?.message ||
            policies.error?.message}
        </p>
      )}
    </>
  );
}
