
import { NextRequest, NextResponse } from "next/server";

export const runtime = "nodejs";
export const dynamic = "force-dynamic";

const MAX_REQUEST_BYTES = 4096;
const MAX_QUESTION_LENGTH = 1500;

function errorResponse(status: number, detail: string) {
  return NextResponse.json(
    { detail },
    {
      status,
      headers: { "Cache-Control": "no-store" },
    }
  );
}

export async function POST(request: NextRequest) {
  // 1. This endpoint is only for explicitly enabled
  // local development. Never enable it in production.
  if (
    process.env.NODE_ENV !== "development" ||
    process.env.EDI_ENABLE_DEV_AGENT_FRONTEND !== "true"
  ) {
    return errorResponse(404, "Not found.");
  }

  // 2. Enforce the local frontend address.
  // This is a development safeguard, not user authentication.
  // Local-development gateway.
  // Next.js must be bound to 127.0.0.1:3000.
  const LOCAL_ORIGIN = "http://127.0.0.1:3000";

  const host = request.headers.get("host");
  const origin = request.headers.get("origin");

  // Validate the requested local host explicitly.
  if (host !== "127.0.0.1:3000") {
    return errorResponse(403, "Local access only.");
  }

  // Only allow requests originating from our local frontend.
  if (origin !== LOCAL_ORIGIN) {
    return errorResponse(403, "Invalid request origin.");
  }

  // 4. Read the private token on the SERVER ONLY.
  const token = process.env.EDI_DEV_AGENT_TOKEN;

  if (!token) {
    return errorResponse(
      503,
      "Agent gateway is not configured."
    );
  }

  // 5. Allow JSON only.
  const contentType = request.headers.get("content-type");

  if (!contentType?.toLowerCase().startsWith("application/json")) {
    return errorResponse(415, "JSON is required.");
  }

  const declaredLength = Number(
    request.headers.get("content-length") || "0"
  );

  if (
    !Number.isFinite(declaredLength) ||
    declaredLength > MAX_REQUEST_BYTES
  ) {
    return errorResponse(413, "Request is too large.");
  }

  // 6. Accept a question and optional resource selections.
  // FastAPI rechecks each selection against session permissions.
  // Never accept grants, credentials or model names from the browser.
  let payload: unknown;

  try {
    const raw = await request.text();

    if (
      new TextEncoder().encode(raw).byteLength >
      MAX_REQUEST_BYTES
    ) {
      return errorResponse(413, "Request is too large.");
    }

    payload = JSON.parse(raw);
  } catch {
    return errorResponse(400, "Invalid JSON request.");
  }

  if (
    !payload ||
    typeof payload !== "object" ||
    Array.isArray(payload)
  ) {
    return errorResponse(422, "Invalid investigation request.");
  }

  const fields = Object.keys(payload);

  if (
    !fields.includes("question") ||
    fields.some(field => !["question", "document_id", "policy_id"].includes(field))
  ) {
    return errorResponse(
      422,
      "Only question, document_id and policy_id fields are permitted."
    );
  }

  const submittedQuestion = (
    payload as { question?: unknown }
  ).question;

  if (typeof submittedQuestion !== "string") {
    return errorResponse(422, "Question must be text.");
  }

  const question = submittedQuestion.trim();

  if (
    question.length === 0 ||
    question.length > MAX_QUESTION_LENGTH
  ) {
    return errorResponse(
      422,
      "Question must contain 1 to 1500 characters."
    );
  }

  const selection = payload as {document_id?: unknown; policy_id?: unknown};
  const hasSelection = "document_id" in selection || "policy_id" in selection;
  if (hasSelection && (
    typeof selection.document_id !== "string" || typeof selection.policy_id !== "string" ||
    !/^[A-Za-z0-9_-]{1,128}$/.test(selection.document_id) ||
    !/^[A-Za-z0-9_-]{1,128}$/.test(selection.policy_id)
  )) return errorResponse(422, "Select both a document and a policy.");

  // 7. Restrict backend requests to local FastAPI.
  const backendValue =
    process.env.BACKEND_API_URL ||
    "http://127.0.0.1:8000";

  let backend: URL;

  try {
    backend = new URL(backendValue);

    if (
      backend.protocol !== "http:" ||
      backend.hostname !== "127.0.0.1" ||
      backend.username ||
      backend.password ||
      backend.search ||
      backend.hash ||
      backend.pathname !== "/"
    ) {
      throw new Error("Invalid local backend configuration");
    }
  } catch {
    return errorResponse(
      503,
      "Local backend URL is not configured correctly."
    );
  }

  // 8. Call FastAPI from the Next.js server.
  // The secret token never enters browser JavaScript.
  try {
    const upstream = await fetch(
      new URL("/agent/investigate", backend),
      {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          "x-edi-agent-token": token,
          "x-csrf-token": request.headers.get("x-csrf-token") || "",
          "Origin": LOCAL_ORIGIN,
          "Cookie": ["edi_session", "__Host-edi_session"].map(name => {
            const value = request.cookies.get(name)?.value;
            return value ? `${name}=${encodeURIComponent(value)}` : "";
          }).filter(Boolean).join("; "),
        },
        body: JSON.stringify({ question, ...(hasSelection ? {document_id: selection.document_id, policy_id: selection.policy_id} : {}) }),
        cache: "no-store",
        signal: AbortSignal.timeout(180_000),
      }
    );

    const result: unknown = await upstream
      .json()
      .catch(() => null);

    if (result === null) {
      return errorResponse(
        502,
        "Invalid response from investigation service."
      );
    }

    const reference = upstream.headers.get("x-request-id");
    const responseHeaders = new Headers({"Cache-Control": "no-store"});
    if (reference && /^[a-f0-9]{32}$/.test(reference)) responseHeaders.set("X-Request-ID", reference);
    return NextResponse.json(result, {
      status: upstream.status,
      headers: responseHeaders,
    });
  } catch {
    return errorResponse(
      502,
      "Investigation service unavailable."
    );
  }
}
