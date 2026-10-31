import { NextRequest, NextResponse } from "next/server";

export const runtime = "nodejs";
export const dynamic = "force-dynamic";

function error(status: number, detail: string) {
  return NextResponse.json(
    { detail },
    { status, headers: { "Cache-Control": "no-store" } },
  );
}

async function proxy(
  request: NextRequest,
  context: { params: Promise<{ path: string[] }> },
) {
  if (
    process.env.NODE_ENV !== "development" ||
    process.env.EDI_ENABLE_DEV_WORKFLOWS_FRONTEND !== "true"
  )
    return error(404, "Not found.");
  let local: URL;
  try {
    local = new URL(
      process.env.EDI_DEV_WORKFLOW_ORIGIN || "http://127.0.0.1:3000",
    );
    if (
      local.protocol !== "http:" ||
      local.hostname !== "127.0.0.1" ||
      !local.port ||
      local.pathname !== "/" ||
      local.username ||
      local.password ||
      local.search ||
      local.hash
    )
      throw new Error("Not loopback");
  } catch {
    return error(
      500,
      "Workflow frontend origin must be a loopback HTTP address.",
    );
  }
  let origin = request.headers.get("origin");
  if (!origin && request.method === "GET") {
    try {
      origin = new URL(request.headers.get("referer") || "").origin;
    } catch {
      origin = null;
    }
  }
  if (
    request.headers.get("host") !== local.host ||
    origin !== local.origin ||
    request.headers.get("sec-fetch-site") === "cross-site"
  )
    return error(403, "Local workflow access only.");
  const token = process.env.EDI_DEV_WORKFLOW_TOKEN;
  if (!token) return error(503, "Workflow gateway is not configured.");
  const path = (await context.params).path.join("/");
  const id = "[A-Za-z0-9_-]{1,128}";
  const allowed =
    request.method === "GET"
      ? new RegExp(`^runs(?:/${id})?$`).test(path)
      : request.method === "POST" &&
        new RegExp(`^runs(?:/${id}/resume)?$`).test(path);
  if (!allowed) return error(404, "Workflow route not found.");
  let base: URL;
  try {
    base = new URL(process.env.BACKEND_API_URL || "http://127.0.0.1:8000");
    if (
      base.protocol !== "http:" ||
      !["127.0.0.1", "localhost", "[::1]"].includes(base.hostname) ||
      base.username ||
      base.password ||
      base.search ||
      base.hash ||
      base.pathname !== "/"
    )
      throw new Error("Bad backend");
  } catch {
    return error(500, "Workflow backend must be a loopback HTTP service.");
  }
  let body: string | undefined;
  if (request.method === "POST") {
    if (
      !request.headers
        .get("content-type")
        ?.toLowerCase()
        .startsWith("application/json")
    )
      return error(415, "Workflow JSON required.");
    let size = 0;
    const chunks: Uint8Array[] = [];
    const reader = request.body?.getReader();
    if (reader)
      for (;;) {
        const part = await reader.read();
        if (part.done) break;
        size += part.value.byteLength;
        if (size > 4096) {
          await reader.cancel();
          return error(413, "Workflow request too large.");
        }
        chunks.push(part.value);
      }
    const bytes = new Uint8Array(size);
    let offset = 0;
    for (const chunk of chunks) {
      bytes.set(chunk, offset);
      offset += chunk.byteLength;
    }
    try {
      const payload = size ? JSON.parse(new TextDecoder().decode(bytes)) : {};
      const keys =
        path === "runs"
          ? ["document_id", "policy_id", "question", "request_key"]
          : [];
      if (
        !payload ||
        typeof payload !== "object" ||
        Array.isArray(payload) ||
        Object.keys(payload).some((key) => !keys.includes(key)) ||
        (path === "runs" &&
          keys.some((key) => typeof payload[key] !== "string"))
      )
        return error(422, "Invalid workflow fields.");
      body = JSON.stringify(payload);
    } catch {
      return error(422, "Invalid workflow JSON.");
    }
  }
  const headers = new Headers({ "x-edi-workflow-token": token });
  for (const key of ["origin", "x-csrf-token", "sec-fetch-site"]) {
    const value = request.headers.get(key);
    if (value) headers.set(key, value);
  }
  const cookie = ["edi_session", "__Host-edi_session"]
    .map((name) => {
      const value = request.cookies.get(name)?.value;
      return value ? `${name}=${encodeURIComponent(value)}` : "";
    })
    .filter(Boolean)
    .join("; ");
  if (cookie) headers.set("cookie", cookie);
  if (body) headers.set("Content-Type", "application/json");
  const suffix = path.slice("runs".length);
  try {
    const upstream = await fetch(
      new URL(`/specialist-workflows${suffix}`, base),
      {
        method: request.method,
        headers,
        body,
        cache: "no-store",
        redirect: "manual",
        signal: AbortSignal.timeout(10000),
      },
    );
    const reference = upstream.headers.get("x-request-id");
    const responseHeaders = new Headers({
      "Content-Type":
        upstream.headers.get("Content-Type") || "application/json",
      "Cache-Control": "no-store",
    });
    if (reference && /^[a-f0-9]{32}$/.test(reference))
      responseHeaders.set("X-Request-ID", reference);
    return new Response(upstream.body, {
      status: upstream.status,
      headers: responseHeaders,
    });
  } catch {
    return error(502, "Workflow service unavailable.");
  }
}

export { proxy as GET, proxy as POST };
