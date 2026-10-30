"use client";

import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useAuth } from "@/components/auth";
import { request } from "@/lib/api";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";

type Requirement = {
  rule_id: string;
  kind: string;
  status: string;
  source_quote: string;
  candidate_document_ids: string[];
  reviewed_document_ids: string[];
  explanation: string;
};
type Candidate = {
  document_id: string;
  filename: string;
  document_type: string;
};

function EvidenceReview({
  item,
  candidates,
  documentId,
  policyId,
}: {
  item: Requirement;
  candidates: Candidate[];
  documentId: string;
  policyId: string;
}) {
  const cache = useQueryClient();
  const [selected, setSelected] = useState<string[]>(
    item.candidate_document_ids,
  );
  const [note, setNote] = useState("");
  const save = useMutation({
    mutationFn: () =>
      request(`/documents/${encodeURIComponent(documentId)}/documentation`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          policy_id: policyId,
          rule_id: item.rule_id,
          evidence_ids: selected,
          note: note.trim(),
        }),
      }),
    onSuccess: () => {
      setNote("");
      cache.invalidateQueries({
        queryKey: ["documentation", documentId, policyId],
      });
      cache.invalidateQueries({ queryKey: ["specialist-runs"] });
    },
  });
  return (
    <form
      className="space-y-3"
      onSubmit={(event) => {
        event.preventDefault();
        save.mutate();
      }}
    >
      <fieldset className="space-y-2">
        <legend className="text-xs font-semibold">
          Reviewed supporting documents (same uploader)
        </legend>
        {candidates.map((candidate) => (
          <div key={candidate.document_id} className="space-y-1 text-xs">
            <label className="flex items-start gap-2">
              <input
                type="checkbox"
                checked={selected.includes(candidate.document_id)}
                disabled={
                  save.isPending ||
                  (!selected.includes(candidate.document_id) &&
                    selected.length >= 5)
                }
                onChange={(event) =>
                  setSelected(
                    event.target.checked
                      ? [...selected, candidate.document_id]
                      : selected.filter((id) => id !== candidate.document_id),
                  )
                }
              />
              <span>
                {candidate.filename} · {candidate.document_type}
                {candidate.document_id === documentId
                  ? " · current uploaded document"
                  : ""}
              </span>
            </label>
            <a
              className="ml-5 text-primary underline"
              href={`/api/bridge/documents/${encodeURIComponent(candidate.document_id)}/original`}
              target="_blank"
              rel="noopener noreferrer"
            >
              Open original
            </a>
          </div>
        ))}
      </fieldset>
      <label className="block text-xs">
        What did you verify?
        <textarea
          aria-label={`Documentation review note ${item.rule_id}`}
          value={note}
          minLength={10}
          maxLength={500}
          required
          className="mt-1 w-full rounded border p-2"
          onChange={(event) => setNote(event.target.value)}
        />
      </label>
      <p className="text-xs text-muted">
        Confirm only after checking the selected original and reviewed fields
        against this policy. This records documentation review, not expense or
        payment approval.
      </p>
      <Button
        size="sm"
        disabled={!selected.length || note.trim().length < 10 || save.isPending}
      >
        Confirm documentation review
      </Button>
      {save.isError && (
        <p role="alert" className="text-xs text-red-700">
          {save.error.message}
        </p>
      )}
      {save.isSuccess && (
        <p role="status" className="text-xs text-green-700">
          Documentation review recorded.
        </p>
      )}
    </form>
  );
}

export function DocumentationChecklist({
  documentId,
  policyId,
}: {
  documentId: string;
  policyId: string;
}) {
  const { user } = useAuth();
  const staff = user?.role === "reviewer" || user?.role === "admin";
  const checklist = useQuery({
    queryKey: ["documentation", documentId, policyId],
    queryFn: () =>
      request<{ status: string; requirements: Requirement[] }>(
        `/documents/${encodeURIComponent(documentId)}/documentation/${encodeURIComponent(policyId)}`,
      ),
    refetchInterval: 3000,
  });
  const evidence = useQuery({
    queryKey: ["documentation-candidates", documentId],
    queryFn: () =>
      request<{ candidates: Candidate[]; truncated: boolean }>(
        `/documents/${encodeURIComponent(documentId)}/documentation-candidates`,
      ),
    enabled: staff && !!checklist.data?.requirements.length,
  });
  return (
    <Card className="space-y-4 p-5">
      <h2 className="font-semibold">Documentation requirements</h2>
      <p className="text-xs text-muted">
        A receipt requirement does not mean your receipt is missing. The
        uploaded receipt can be considered as evidence after explicit reviewer
        verification.
      </p>
      {checklist.isLoading ? (
        <p>Loading requirements…</p>
      ) : checklist.isError ? (
        <p role="alert">{checklist.error.message}</p>
      ) : checklist.data?.status === "needs_document_review" ? (
        <p>
          Review the extracted document fields before assessing documentation
          requirements.
        </p>
      ) : checklist.data?.status === "needs_policy_review" ? (
        <p>
          Approved policy evidence is missing, changed or does not cover this
          document. Ask a reviewer to check the policy.
        </p>
      ) : !checklist.data?.requirements.length ? (
        <p className="text-sm">
          No documentation requirement was triggered by the currently applicable
          approved rules. This does not establish full compliance.
        </p>
      ) : (
        checklist.data.requirements.map((item) => (
          <section key={item.rule_id} className="space-y-3 rounded border p-4">
            <h3 className="text-sm font-semibold">
              {item.kind === "unspecified"
                ? "Policy clarification needed"
                : `Required ${item.kind}`}{" "}
              · {item.status.replaceAll("_", " ")}
            </h3>
            <blockquote
              dir="auto"
              className="border-l-2 border-primary pl-3 text-sm"
            >
              {item.source_quote}
            </blockquote>
            <p className="text-xs text-muted">{item.explanation}</p>
            {item.status === "reviewed_satisfied" && (
              <p className="text-sm text-green-700">
                Supporting documentation was explicitly reviewed. Expense
                approval remains separate.
              </p>
            )}
            {staff &&
              item.kind !== "unspecified" &&
              item.status !== "reviewed_satisfied" && (
                <EvidenceReview
                  item={item}
                  candidates={evidence.data?.candidates || []}
                  documentId={documentId}
                  policyId={policyId}
                />
              )}
          </section>
        ))
      )}
      {evidence.isError && <p role="alert">{evidence.error.message}</p>}
      {evidence.data?.truncated && (
        <p className="text-xs text-muted">
          Showing up to 50 recent reviewed documents for this uploader.
        </p>
      )}
    </Card>
  );
}
