
"use client";

import { useState, type FormEvent } from "react";
import Link from "next/link";
import { useQuery } from "@tanstack/react-query";
import { api } from "@/lib/api";
import {
  AlertCircle,
  ArrowRight,
  BookOpenCheck,
  BrainCircuit,
  CheckCircle2,
  FileSearch,
  FileText,
  LoaderCircle,
  LockKeyhole,
  Search,
  ShieldCheck,
  Sparkles,
} from "lucide-react";

import { SectionHeading } from "@/components/feedback";
import { Button } from "@/components/ui/button";
import { Card, CardHeader, CardTitle } from "@/components/ui/card";
import {
  investigateDocument,
  type InvestigationResult,
} from "@/lib/agent-api";
import { labelize } from "@/lib/utils";

const toolNames: Record<string, string> = {
  inspect_document: "Inspect reviewed document",
  get_policy_evidence: "Retrieve approved policy evidence",
  evaluate_document_policy: "Evaluate policy requirements",
};

const reasonMessages: Record<string, string> = {
  investigation_incomplete:
    "The investigation could not establish a verified decision.",
  missing_policy_result:
    "No authoritative policy evaluation was returned.",
  missing_evaluation:
    "The policy evaluation is missing.",
  missing_evidence:
    "Required supporting evidence is missing.",
  missing_action_evidence:
    "A required action does not have supporting policy evidence.",
  invalid_evaluation:
    "The policy evaluation was inconsistent or invalid.",
};

export default function InvestigationClient({unavailableReason}: {unavailableReason: string | null}) {
  const [documentId, setDocumentId] = useState("");
  const [policyId, setPolicyId] = useState("");
  const documents = useQuery({queryKey: ["documents"], queryFn: api.documents, enabled: !unavailableReason});
  const policies = useQuery({queryKey: ["policies"], queryFn: api.policies, enabled: !unavailableReason});
  const selectedDocument = documents.data?.find(d => d.document_id === documentId) || documents.data?.[0];
  const selectedPolicy = policies.data?.find(p => p.policy_id === policyId) || policies.data?.[0];
  const resourcesReady = !!selectedDocument && !!selectedPolicy && !documents.isError && !policies.isError;
  const [question, setQuestion] = useState("");
  const [running, setRunning] = useState(false);
  const [result, setResult] =
    useState<InvestigationResult | null>(null);
  const [error, setError] = useState<string | null>(null);

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();

    const submittedQuestion = question.trim();

    if (unavailableReason || !resourcesReady || !submittedQuestion || running) {
      return;
    }

    setRunning(true);
    setResult(null);
    setError(null);

    try {
      const investigation = await investigateDocument(
        submittedQuestion,
        {document_id: selectedDocument!.document_id, policy_id: selectedPolicy!.policy_id}
      );

      setResult(investigation);
    } catch (caught) {
      setError(
        caught instanceof Error
          ? caught.message
          : "An unexpected investigation error occurred."
      );
    } finally {
      setRunning(false);
    }
  }

  const answer =
    result?.status === "ready" ? result.answer : null;

  return (
    <div className="space-y-6">
      <SectionHeading
        eyebrow="Agentic document intelligence"
        title="Investigation Workspace"
        description="Ask an enterprise document question, investigate approved policy rules, and review evidence-backed decisions."
        action={
          <Button asChild variant="secondary">
            <Link href="/documents">
              <FileText size={16} />
              Document library
            </Link>
          </Button>
        }
      />

      {unavailableReason && <Card role="status" className="border-[#f1d8b0] bg-[#fffaf2] p-6"><h2 className="text-sm font-semibold">AI investigation unavailable</h2><p className="mt-2 text-sm text-muted">{unavailableReason}</p><p className="mt-2 text-xs text-muted">You can still review documents and evaluate approved policy rules from the document page.</p></Card>}

      {/* Introduction */}
      <div className="relative overflow-hidden rounded-[22px] bg-gradient-to-r from-[#242b52] via-[#353b79] to-[#5553be] px-7 py-8 text-white sm:px-9">
        <div className="absolute -right-14 -top-24 h-64 w-64 rounded-full border-[42px] border-white/[.045]" />

        <div className="relative">
          <div className="mb-4 inline-flex items-center gap-2 rounded-full border border-white/20 bg-white/10 px-3 py-1.5 text-[11px] font-semibold text-[#d6d5ff]">
            <Sparkles size={14} />
            Controlled AI investigation
          </div>

          <h2 className="max-w-2xl text-2xl font-bold tracking-tight">
            From a question to a traceable policy decision.
          </h2>

          <p className="mt-3 max-w-2xl text-[13px] leading-7 text-[#d8dcf5]">
            Gemini selects investigation tools. The EDI backend
            verifies reviewed documents and approved policy
            evidence, then evaluates requirements using
            deterministic Python rules.
          </p>

          <div className="mt-5 flex flex-wrap gap-3">
            <span className="flex items-center gap-2 text-[11px] text-[#e5e4ff]">
              <ShieldCheck size={15} />
              Evidence-backed answers
            </span>
            <span className="flex items-center gap-2 text-[11px] text-[#e5e4ff]">
              <LockKeyhole size={15} />
              Local development access
            </span>
          </div>
        </div>
      </div>

      <div className="grid items-start gap-6 xl:grid-cols-[1.5fr_1fr]">
        <div className="space-y-6">
          {/* Question input */}
          <Card>
            <CardHeader>
              <div>
                <CardTitle>Ask an investigation question</CardTitle>
                <p className="mt-1 text-[12px] text-muted">
                  The agent can investigate the documents and
                  policies authorized by the backend.
                </p>
              </div>
              <BrainCircuit size={21} className="text-primary" />
            </CardHeader>

            <form onSubmit={handleSubmit} className="px-6 pb-6">
              <div className="mb-5 grid gap-4 sm:grid-cols-2">
                <label className="text-xs font-semibold">Document<select aria-label="Investigation document" className="mt-2 w-full rounded-xl border border-stroke bg-white p-3 text-sm" value={selectedDocument?.document_id || ""} disabled={running || !!unavailableReason || documents.isLoading} onChange={e => {setDocumentId(e.target.value); setResult(null); setError(null);}}><option value="">Choose a document</option>{documents.data?.map(d => <option key={d.document_id} value={d.document_id}>{d.filename}</option>)}</select></label>
                <label className="text-xs font-semibold">Policy<select aria-label="Investigation policy" className="mt-2 w-full rounded-xl border border-stroke bg-white p-3 text-sm" value={selectedPolicy?.policy_id || ""} disabled={running || !!unavailableReason || policies.isLoading} onChange={e => {setPolicyId(e.target.value); setResult(null); setError(null);}}><option value="">Choose a policy</option>{policies.data?.map(p => <option key={p.policy_id} value={p.policy_id}>{p.filename}</option>)}</select></label>
              </div>
              {!unavailableReason && (documents.isLoading || policies.isLoading) && <p role="status" className="mb-4 text-sm text-muted">Loading your documents and policies…</p>}
              {!unavailableReason && (documents.isError || policies.isError) && <div role="alert" className="mb-4 text-sm text-red-700">Could not load your documents or policies. <button type="button" className="underline" onClick={() => {documents.refetch(); policies.refetch();}}>Retry</button></div>}
              {!unavailableReason && documents.isSuccess && !documents.data.length && <p className="mb-4 text-sm text-muted">Upload a document to start. <Link href="/upload" className="text-primary underline">Upload document</Link></p>}
              {!unavailableReason && policies.isSuccess && !policies.data.length && <p className="mb-4 text-sm text-muted">Your organization needs a policy. <Link href="/policies" className="text-primary underline">Open policy library</Link></p>}
              {!unavailableReason && selectedDocument && !["approved", "corrected"].includes(selectedDocument.review_status) && <p className="mb-4 text-sm text-muted">This document still needs a reviewer to approve or correct its extracted fields before a verified policy decision is available.</p>}
              <label
                htmlFor="investigation-question"
                className="mb-2 block text-[12px] font-semibold text-ink"
              >
                Your question
              </label>

              <textarea
                id="investigation-question"
                value={question}
                onChange={(event) =>
                  setQuestion(event.target.value)
                }
                placeholder="For example: Investigate my $175 meal receipt against the company expense policy. What actions are required?"
                maxLength={1500}
                rows={5}
                disabled={running || !!unavailableReason}
                className="w-full resize-y rounded-xl border border-stroke bg-[#fcfdff] p-4 text-[13px] leading-7 text-ink outline-none transition-colors placeholder:text-[#9ba5b6] focus:border-primary focus:ring-2 focus:ring-primary/10 disabled:opacity-60"
              />

              <div className="mt-3 flex flex-wrap items-center justify-between gap-3">
                <span className="text-[11px] text-muted">
                  {question.length} / 1500 characters
                </span>

                <Button
                  type="submit"
                  disabled={!!unavailableReason || !resourcesReady || !question.trim() || running}
                  size="lg"
                >
                  {running ? (
                    <>
                      <LoaderCircle
                        size={17}
                        className="animate-spin"
                      />
                      Investigating...
                    </>
                  ) : (
                    <>
                      <Search size={17} />
                      Run investigation
                      <ArrowRight size={16} />
                    </>
                  )}
                </Button>
              </div>

              <p className="mt-4 text-[11px] leading-5 text-muted">
                Submitting a question starts a real Gemini
                investigation and may consume API quota.
                No approvals or reimbursements are executed.
              </p>
            </form>
          </Card>

          {/* Request error */}
          {error && (
            <div
              role="alert"
              className="flex items-start gap-3 rounded-2xl border border-[#ffd5d8] bg-[#fff5f5] p-5"
            >
              <AlertCircle
                size={19}
                className="mt-0.5 shrink-0 text-[#c84a5b]"
              />
              <div>
                <h3 className="text-[13px] font-semibold text-[#963441]">
                  Investigation request failed
                </h3>
                <p className="mt-1 break-words text-[12px] leading-6 text-[#a35460]">
                  {error}
                </p>
              </div>
            </div>
          )}

          {/* Running indicator */}
          {running && (
            <Card
              role="status"
              aria-live="polite"
              className="flex items-center gap-4 p-6"
            >
              <div className="rounded-xl bg-[#f0efff] p-3 text-primary">
                <LoaderCircle
                  size={22}
                  className="animate-spin"
                />
              </div>
              <div>
                <h3 className="text-[13px] font-semibold text-ink">
                  Investigation in progress
                </h3>
                <p className="mt-1 text-[12px] text-muted">
                  The agent is checking authorized documents
                  and approved rules. The tool trace will
                  appear when the request completes.
                </p>
              </div>
            </Card>
          )}

          {/* Verified answer */}
          {answer && (
            <Card className="overflow-hidden">
              <div className="border-b border-[#f0e3c7] bg-[#fffaf0] p-6">
                <div className="mb-3 flex flex-wrap items-center gap-2">
                  <span className="rounded-full bg-[#fff0ce] px-3 py-1 text-[11px] font-bold text-[#a47324]">
                    {labelize(answer.policy_outcome)}
                  </span>
                  <span className="flex items-center gap-1.5 text-[11px] font-semibold text-[#49745e]">
                    <CheckCircle2 size={14} />
                    Evidence-backed result
                  </span>
                </div>

                <h2 className="text-[19px] font-bold tracking-tight text-ink">
                  {answer.summary}
                </h2>

                <p className="mt-2 text-[12px] leading-6 text-muted">
                  This decision is derived from the deterministic
                  policy evaluator, not Gemini's unverified draft.
                </p>
              </div>

              <div className="space-y-6 p-6">
                <section>
                  <h3 className="mb-4 text-[13px] font-bold text-ink">
                    Required actions
                  </h3>

                  {answer.required_actions.length === 0 ? (
                    <p className="rounded-xl bg-[#f4f8f6] p-4 text-[12px] leading-6 text-[#50745c]">
                      No additional actions were triggered
                      by the evaluated approved rules.
                    </p>
                  ) : (
                    <div className="space-y-4">
                      {answer.required_actions.map(
                        (action, index) => (
                          <div
                            key={`${action.rule_id}-${index}`}
                            className="rounded-xl border border-stroke p-4"
                          >
                            <div className="flex items-start gap-3">
                              <div className="flex h-8 w-8 shrink-0 items-center justify-center rounded-lg bg-[#fff3d9] text-[#a87421]">
                                <span className="text-[12px] font-bold">
                                  {index + 1}
                                </span>
                              </div>

                              <div className="min-w-0 flex-1">
                                <div className="text-[13px] font-bold text-ink">
                                  {action.requirement}
                                </div>

                                <div className="mt-1 break-all font-mono text-[10px] text-muted">
                                  Rule: {action.rule_id}
                                </div>
                              </div>
                            </div>

                            <blockquote dir="auto" className="mt-4 border-l-[3px] border-primary bg-[#f8f7ff] px-4 py-3 text-[12px] leading-6 text-[#515a78]">
                              {action.source_quote}
                            </blockquote>

                            {action.source_chunk_id && (
                              <div className="mt-3 break-all font-mono text-[10px] text-[#929bb0]">
                                Source chunk: {action.source_chunk_id}
                              </div>
                            )}
                          </div>
                        )
                      )}
                    </div>
                  )}
                </section>

                <section className="rounded-xl border border-[#dde8e4] bg-[#f5faf7] p-4">
                  <div className="flex items-center gap-2 text-[#377f61]">
                    <ShieldCheck size={17} />
                    <h3 className="text-[12px] font-bold">
                      Evaluation boundaries
                    </h3>
                  </div>

                  <p className="mt-2 text-[12px] leading-6 text-[#557264]">
                    {answer.notice}
                  </p>

                  <div className="mt-3 text-[11px] text-[#648172]">
                    Coverage: {labelize(answer.coverage)}
                  </div>

                  <div className="mt-1 text-[11px] text-[#648172]">
                    Full compliance certified: No
                  </div>
                </section>

                <div className="flex flex-wrap items-center gap-3">
                  <Button asChild variant="secondary" size="sm">
                    <Link
                      href={`/documents/${encodeURIComponent(
                        answer.document_id
                      )}`}
                    >
                      <FileText size={15} />
                      View document
                    </Link>
                  </Button>

                  <Button asChild variant="secondary" size="sm">
                    <Link href="/policies">
                      <BookOpenCheck size={15} />
                      Policy library
                    </Link>
                  </Button>
                </div>
              </div>
            </Card>
          )}

          {/* Incomplete investigation */}
          {result?.status === "not_ready" && (
            <Card className="border-[#f1d8b0] bg-[#fffaf2] p-6">
              <div className="flex items-center gap-3">
                <AlertCircle
                  size={20}
                  className="text-[#af802c]"
                />
                <h2 className="text-[15px] font-bold text-ink">
                  Verified decision unavailable
                </h2>
              </div>

              <p className="mt-3 text-[12px] leading-6 text-muted">
                {reasonMessages[result.reason] ??
                  labelize(result.reason)}
              </p>

              <p className="mt-2 text-[11px] text-muted">
                EDI did not return an official policy decision.
                Review the tool trace before trying again.
              </p>
            </Card>
          )}

          {/* Initial empty state */}
          {!unavailableReason && resourcesReady && !running && !result && !error && (
            <Card className="flex flex-col items-center p-9 text-center">
              <div className="mb-4 rounded-2xl bg-[#f0efff] p-4 text-primary">
                <FileSearch size={27} />
              </div>

              <h2 className="text-[15px] font-bold text-ink">
                Ready for investigation
              </h2>

              <p className="mt-2 max-w-md text-[12px] leading-6 text-muted">
                Submit a question to start an investigation.
                Results will appear here with supporting
                policy quotes and required actions.
              </p>
            </Card>
          )}
        </div>

        {/* Right-hand execution panel */}
        <div className="space-y-6">
          <Card>
            <CardHeader>
              <div>
                <CardTitle>Agent execution trace</CardTitle>
                <p className="mt-1 text-[12px] text-muted">
                  Tools called during this investigation.
                </p>
              </div>
              <BrainCircuit
                size={20}
                className="text-primary"
              />
            </CardHeader>

            <div className="px-6 pb-6">
              {result?.tool_trace.length ? (
                <ol className="space-y-4">
                  {result.tool_trace.map((step, index) => (
                    <li
                      key={`${step.tool}-${index}`}
                      className="flex items-start gap-3"
                    >

                      <div
                        className={`flex h-9 w-9 shrink-0 items-center justify-center rounded-xl ${
                          step.status === "ready" || step.status === "passed"
                            ? "bg-[#eff8f3] text-[#2e9870]"
                            : [
                                "access_denied",
                                "not_found",
                                "invalid_arguments",
                                "unknown_tool",
                                "policy_violation",
                              ].includes(step.status)
                            ? "bg-[#fff1f2] text-[#be123c]"
                            : "bg-[#fff7e6] text-[#b7791f]"
                        }`}
                      >
                        {step.status === "ready" || step.status === "passed" ? (
                          <CheckCircle2 size={18} />
                        ) : (
                          <AlertCircle size={18} />
                        )}
                      </div>


                      <div className="min-w-0 flex-1">
                        <div className="break-words text-[12px] font-semibold text-ink">
                          {toolNames[step.tool] ??
                            labelize(step.tool)}
                        </div>

                        <div className="mt-1 text-[11px] text-muted">
                          Status: {labelize(step.status)}
                        </div>
                      </div>
                    </li>
                  ))}
                </ol>
              ) : (
                <div className="rounded-xl bg-[#f7f8fc] p-5 text-center">
                  <BrainCircuit
                    size={24}
                    className="mx-auto text-[#a7aacb]"
                  />
                  <p className="mt-3 text-[12px] leading-6 text-muted">
                    {running
                      ? "Collecting investigation results..."
                      : "No investigation tools have been executed yet."}
                  </p>
                </div>
              )}
            </div>
          </Card>

          <Card className="p-6">
            <div className="flex items-center gap-3">
              <div className="rounded-xl bg-[#f0efff] p-3 text-primary">
                <ShieldCheck size={20} />
              </div>
              <div className="text-[13px] font-bold text-ink">
                Trust and verification
              </div>
            </div>

            <div className="mt-5 space-y-4 text-[12px] leading-6 text-muted">
              <p>
                <strong className="text-ink">
                  Controlled tools:
                </strong>{" "}
                The model can only use tools made available
                by the backend.
              </p>
              <p>
                <strong className="text-ink">
                  Reviewed records:
                </strong>{" "}
                Document and policy checks enforce the
                server's authorized resource scope.
              </p>
              <p>
                <strong className="text-ink">
                  Deterministic decisions:
                </strong>{" "}
                Policy requirements are calculated by
                Python instead of relying on model opinion.
              </p>
              <p>
                <strong className="text-ink">
                  Human oversight:
                </strong>{" "}
                An investigation never grants reimbursement
                approval or certifies full compliance.
              </p>
            </div>
          </Card>
        </div>
      </div>
    </div>
  );
}
