
export interface InvestigationToolStep {
  tool: string;
  status: string;
}

export interface InvestigationAction {
  rule_id: string;
  requirement: string;
  source_quote: string;
  source_chunk_id: string | null;
}

export interface VerifiedInvestigationAnswer {
  status: "ready";
  document_id: string;
  policy_id: string;
  policy_outcome: string;
  summary: string;
  required_actions: InvestigationAction[];
  coverage: "approved_rules_only";
  full_compliance_certified: false;
  notice: string;
}

export type InvestigationResult =
  | {
      status: "ready";
      answer: VerifiedInvestigationAnswer;
      tool_trace: InvestigationToolStep[];
    }
  | {
      status: "not_ready";
      reason: string;
      tool_trace: InvestigationToolStep[];
    };

export async function investigateDocument(
  question: string
): Promise<InvestigationResult> {
  const response = await fetch("/api/agent/investigate", {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify({
      question: question.trim(),
    }),
    cache: "no-store",
  });

  const data: unknown = await response
    .json()
    .catch(() => null);

  if (!response.ok) {
    let message = `Investigation failed (HTTP ${response.status}).`;

    if (
      data &&
      typeof data === "object" &&
      "detail" in data &&
      typeof data.detail === "string"
    ) {
      message = data.detail;
    }

    throw new Error(message);
  }

  if (
    !data ||
    typeof data !== "object" ||
    !("status" in data) ||
    !("tool_trace" in data) ||
    !Array.isArray(data.tool_trace)
  ) {
    throw new Error("Invalid investigation response.");
  }

  if (data.status === "ready") {
    if (
      !("answer" in data) ||
      !data.answer ||
      typeof data.answer !== "object" ||
      !("required_actions" in data.answer) ||
      !Array.isArray(data.answer.required_actions)
    ) {
      throw new Error("Missing verified investigation answer.");
    }

    return data as InvestigationResult;
  }

  if (
    data.status === "not_ready" &&
    "reason" in data &&
    typeof data.reason === "string"
  ) {
    return data as InvestigationResult;
  }

  throw new Error("Unexpected investigation status.");
}
