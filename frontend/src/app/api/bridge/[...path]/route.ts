import { NextRequest, NextResponse } from "next/server";

export const runtime = "nodejs";
export const dynamic = "force-dynamic";

// Deliberately narrow API gateway. No arbitrary upstream URL, credentials, or host.
function isAllowed(method: string, path: string) {
  const id = "[a-zA-Z0-9_-]+";
  const patterns: Record<string, RegExp[]> = {
    GET: [
      /^(health|ready)$/,
      /^auth\/(csrf|me|profile)$/,
      /^admin\/users$/,
      /^policies$/,
      new RegExp(`^policies/${id}/(original|processing)$`),
      /^documents$/,
      new RegExp(`^documents/${id}$`),
      new RegExp(`^documents/${id}/(audit|original|reviews|processing)$`),
      /^reviews\/pending$/,
      new RegExp(`^policies/${id}/rules$`),
    ],
    POST: [
      /^auth\/(login|logout|profile|change-password)$/,
      /^admin\/users$/,
      new RegExp(`^admin/users/${id}/(status|profile)$`),
      new RegExp(`^policies/${id}/rules/(extract-candidates|extract-all|approve-all)$`),
      new RegExp(`^policies/${id}/rules/${id}/decision$`),
      new RegExp(`^(documents|policies)/${id}/processing/retry$`),
      /^documents\/upload$/,
      /^policies\/upload$/,
      new RegExp(`^documents/${id}/review$`),
      new RegExp(`^documents/${id}/validate-approved-policy$`),
    ],
  };
  return patterns[method]?.some((pattern) => pattern.test(path)) ?? false;
}

async function proxy(request: NextRequest, context: { params: Promise<{ path: string[] }> }) {
  const { path: segments } = await context.params;
  const path = segments.join("/");
  if (!isAllowed(request.method, path)) return NextResponse.json({ detail: "Route not available through this frontend." }, { status: 404 });

  const backend = process.env.BACKEND_API_URL || "http://127.0.0.1:8000";
  let baseUrl: URL;
  try {
    baseUrl = new URL(backend);
    if (!["http:", "https:"].includes(baseUrl.protocol) || baseUrl.username || baseUrl.password || baseUrl.search || baseUrl.hash) throw new Error("Bad URL");
  } catch {
    return NextResponse.json({ detail: "BACKEND_API_URL is misconfigured." }, { status: 500 });
  }

  const maxUpload = 20 * 1024 * 1024;
  const length = Number(request.headers.get("content-length") || "0");
  if (request.method === "POST" && length > maxUpload) return NextResponse.json({ detail: "Upload exceeds the 20 MB frontend limit." }, { status: 413 });

  try {
    const headers = new Headers();
    const contentType = request.headers.get("content-type");
    if (contentType) headers.set("Content-Type", contentType);
    const cookie = ["edi_session", "__Host-edi_session"].map(name => {
      const value = request.cookies.get(name)?.value;
      return value ? `${name}=${encodeURIComponent(value)}` : "";
    }).filter(Boolean).join("; ");
    if (cookie) headers.set("Cookie", cookie);
    for (const name of ["x-csrf-token", "origin", "sec-fetch-site"]) {
      const value = request.headers.get(name);
      if (value) headers.set(name, value);
    }
    let body: Uint8Array<ArrayBuffer> | undefined;
    if (request.method === "POST" && request.body) {
      const reader = request.body.getReader();
      const chunks: Uint8Array[] = [];
      let size = 0;
      while (true) {
        const {done, value} = await reader.read();
        if (done) break;
        size += value.byteLength;
        if (size > maxUpload) {
          await reader.cancel();
          return NextResponse.json({detail: "Request exceeds the 20 MB limit."}, {status: 413});
        }
        chunks.push(value);
      }
      body = new Uint8Array(size);
      let offset = 0;
      for (const chunk of chunks) { body.set(chunk, offset); offset += chunk.byteLength; }
    }
    if (body && body.byteLength > maxUpload) return NextResponse.json({ detail: "Request exceeds the 20 MB limit." }, { status: 413 });
    const target = new URL(`${baseUrl.pathname.replace(/\/$/, "")}/${path}`, baseUrl.origin);
    const upstream = await fetch(target, {
      method: request.method,
      redirect: "manual",
      body: body?.byteLength ? body : undefined,
      headers,
      cache: "no-store",
      signal: AbortSignal.timeout(180000),
    });
    const returnHeaders = new Headers({ "Cache-Control": "no-store" });
    for (const name of ["content-type", "content-disposition"]) {
      const value = upstream.headers.get(name);
      if (value) returnHeaders.set(name, value);
    }
    for (const cookie of upstream.headers.getSetCookie()) returnHeaders.append("Set-Cookie", cookie);
    return new Response(upstream.body, { status: upstream.status, headers: returnHeaders });
  } catch {
    return NextResponse.json({ detail: "FastAPI is unavailable or did not respond in time. Start the backend on port 8000." }, { status: 502 });
  }
}

export { proxy as GET, proxy as POST };
