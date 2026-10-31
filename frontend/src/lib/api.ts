import type { AuditEvent, DocumentDetail, DocumentSummary, PendingReview, PolicyRulesResponse, PolicyUploadResponse, ReviewEvent, UploadResponse, ValidationResult } from "@/lib/types";

const ROOT = "/api/bridge";

export class ApiError extends Error {
  public readonly requestId?: string;
  constructor(message: string, public readonly status: number, public readonly details: unknown, requestId?: string | null) {
    super(message);
    this.name = "ApiError";
    this.requestId = requestId && /^[a-f0-9]{32}$/.test(requestId) ? requestId : undefined;
  }
}

function detailMessage(body: unknown, fallback: string): string {
  if (body && typeof body === "object" && "detail" in body) {
    const detail = (body as { detail: unknown }).detail;
    if (typeof detail === "string") return detail;
    if (detail && typeof detail === "object" && "message" in detail) {
      return String((detail as { message: unknown }).message);
    }
  }
  return fallback;
}

export async function request<T>(path: string, init?: RequestInit): Promise<T> {
  let response: Response;
  try {
    const headers = new Headers(init?.headers);
    if (init?.method && !["GET", "HEAD"].includes(init.method)) {
      const security = await csrfHeaders();
      headers.set("x-csrf-token", security["x-csrf-token"]);
    }
    response = await fetch(`${ROOT}${path}`, { cache: "no-store", ...init, headers });
  } catch (error) {
    if (error instanceof ApiError) throw error;
    throw new ApiError("Cannot reach the frontend API proxy. Is Next.js running?", 0, null);
  }
  const body: unknown = await response.json().catch(() => null);
  if (response.status === 401 && path !== "/auth/login") window.dispatchEvent(new Event("edi-session-expired"));
  if (!response.ok) throw new ApiError(detailMessage(body, `Request failed (${response.status})`), response.status, body, response.headers.get("x-request-id"));
  return body as T;
}

export async function csrfHeaders(): Promise<Record<string, string>> {
  const response = await fetch(`${ROOT}/auth/csrf`, { cache: "no-store" });
  const data: unknown = await response.json().catch(() => null);
  if (!response.ok) throw new ApiError(detailMessage(data, `Cannot establish a secure session (${response.status}).`), response.status, data, response.headers.get("x-request-id"));
  if (!data || typeof data !== "object" || !("csrf_token" in data) || typeof data.csrf_token !== "string" || !data.csrf_token) {
    throw new ApiError("The session service returned an invalid response.", response.status, null);
  }
  return { "x-csrf-token": data.csrf_token };
}

export const api = {
  policies: () => request<{policy_id: string; filename: string; added_at: string}[]>("/policies"),
  extractPolicy: (id: string) => request(`/policies/${encodeURIComponent(id)}/rules/extract-all`, { method: "POST" }),
  approveAllRules: (id: string, rule_ids: string[]) => request(`/policies/${encodeURIComponent(id)}/rules/approve-all`, {method: "POST", headers: {"Content-Type":"application/json"}, body: JSON.stringify({rule_ids})}),
  decideRule: (id: string, rule: string, decision: "approve" | "reject") => request(`/policies/${encodeURIComponent(id)}/rules/${encodeURIComponent(rule)}/decision`, { method: "POST", headers: {"Content-Type":"application/json"}, body: JSON.stringify({decision}) }),
  health: () => request<{ status: string }>("/health"),
  documents: () => request<DocumentSummary[]>("/documents"),
  document: (id: string) => request<DocumentDetail>(`/documents/${encodeURIComponent(id)}`),
  pendingReviews: () => request<PendingReview[]>("/reviews/pending"),
  audit: (id: string) => request<AuditEvent[]>(`/documents/${encodeURIComponent(id)}/audit`),
  reviews: (id: string) => request<ReviewEvent[]>(`/documents/${encodeURIComponent(id)}/reviews`),
  upload: (file: File) => { const data = new FormData(); data.append("file", file); return request<UploadResponse>("/documents/upload", { method: "POST", body: data }); },
  uploadPolicy: (file: File) => { const data = new FormData(); data.append("file", file); return request<PolicyUploadResponse>("/policies/upload", { method: "POST", body: data }); },
  review: (id: string, body: { decision: "approved" | "corrected" | "rejected"; reviewer: string; corrections?: Record<string, unknown>; notes?: string }) =>
    request<{ review_status: string }>(`/documents/${encodeURIComponent(id)}/review`, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body) }),
  validate: (documentId: string, policyId: string) =>
    request<ValidationResult>(`/documents/${encodeURIComponent(documentId)}/validate-approved-policy`, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ policy_id: policyId }) }),
  policyRules: (id: string) => request<PolicyRulesResponse>(`/policies/${encodeURIComponent(id)}/rules`),
  originalUrl: (id: string) => `${ROOT}/documents/${encodeURIComponent(id)}/original`,
};
