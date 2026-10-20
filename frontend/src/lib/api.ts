import type { AuditEvent, DocumentDetail, DocumentSummary, PendingReview, PolicyRulesResponse, PolicyUploadResponse, ReviewEvent, UploadResponse, ValidationResult } from "@/lib/types";

const ROOT = "/api/bridge";

export class ApiError extends Error {
  constructor(message: string, public readonly status: number, public readonly details: unknown) {
    super(message);
    this.name = "ApiError";
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
    response = await fetch(`${ROOT}${path}`, { cache: "no-store", ...init });
  } catch {
    throw new ApiError("Cannot reach the frontend API proxy. Is Next.js running?", 0, null);
  }
  const body: unknown = await response.json().catch(() => null);
  if (!response.ok) throw new ApiError(detailMessage(body, `Request failed (${response.status})`), response.status, body);
  return body as T;
}

export const api = {
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
