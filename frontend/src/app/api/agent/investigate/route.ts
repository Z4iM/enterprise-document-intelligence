
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

  // 6. Accept ONLY a question.
  // Never accept permissions, credentials or model names
  // from the browser.
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
    fields.length !== 1 ||
    fields[0] !== "question"
  ) {
    return errorResponse(
      422,
      "Only the question field is permitted."
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
        },
        body: JSON.stringify({ question }),
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

    return NextResponse.json(result, {
      status: upstream.status,
      headers: {
        "Cache-Control": "no-store",
      },
    });
  } catch {
    return errorResponse(
      502,
      "Investigation service unavailable."
    );
  }
}
