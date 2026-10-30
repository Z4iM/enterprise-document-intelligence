import { test, expect } from "@playwright/test";
import { NextRequest } from "next/server";
import { GET, POST } from "../src/app/api/workflows/[...path]/route";

const variables = [
  "NODE_ENV",
  "EDI_ENABLE_DEV_WORKFLOWS_FRONTEND",
  "EDI_DEV_WORKFLOW_TOKEN",
  "EDI_DEV_WORKFLOW_ORIGIN",
  "BACKEND_API_URL",
];
let saved: Record<string, string | undefined>;
let original: typeof fetch;
let forwarded: { url: string; init?: RequestInit }[];
test.beforeEach(() => {
  saved = Object.fromEntries(variables.map((key) => [key, process.env[key]]));
  Object.assign(process.env, {
    NODE_ENV: "development",
    EDI_ENABLE_DEV_WORKFLOWS_FRONTEND: "true",
    EDI_DEV_WORKFLOW_TOKEN: "synthetic-workflow-token",
    EDI_DEV_WORKFLOW_ORIGIN: "http://127.0.0.1:3000",
    BACKEND_API_URL: "http://127.0.0.1:8000",
  });
  original = globalThis.fetch;
  forwarded = [];
  globalThis.fetch = async (url, init) => {
    forwarded.push({ url: String(url), init });
    return Response.json({ status: "queued" }, { status: 202 });
  };
});
test.afterEach(() => {
  globalThis.fetch = original;
  for (const key of variables) {
    if (saved[key] === undefined) delete process.env[key];
    else process.env[key] = saved[key];
  }
});

function request(payload: object) {
  return new NextRequest("http://127.0.0.1:3000/api/workflows/runs", {
    method: "POST",
    headers: {
      host: "127.0.0.1:3000",
      origin: "http://127.0.0.1:3000",
      "Content-Type": "application/json",
      cookie: "edi_session=synthetic-session; unrelated=not-forwarded",
      "x-csrf-token": "synthetic-csrf",
    },
    body: JSON.stringify(payload),
  });
}
const context = { params: Promise.resolve({ path: ["runs"] }) };
const body = {
  document_id: "synthetic-doc",
  policy_id: "synthetic-policy",
  question: "Check this",
  request_key: "synthetic-request-key",
};

test("workflow gateway preserves session/CSRF and injects private server token", async () => {
  expect((await POST(request(body), context)).status).toBe(202);
  expect(forwarded[0].url).toBe("http://127.0.0.1:8000/specialist-workflows");
  const headers = new Headers(forwarded[0].init?.headers);
  expect(headers.get("x-edi-workflow-token")).toBe("synthetic-workflow-token");
  expect(headers.get("x-csrf-token")).toBe("synthetic-csrf");
  expect(headers.get("cookie")).toBe("edi_session=synthetic-session");
  expect(forwarded[0].init?.redirect).toBe("manual");
});

for (const extra of [
  { role: "admin" },
  { allowed_document_ids: ["foreign"] },
  { approved: true },
  { token: "browser-token" },
]) {
  test(`workflow gateway rejects permission/control injection ${Object.keys(extra)[0]}`, async () => {
    expect((await POST(request({ ...body, ...extra }), context)).status).toBe(
      422,
    );
    expect(forwarded).toHaveLength(0);
  });
}

test("workflow GET permits same-origin referer without weakening cross-site checks", async () => {
  const req = new NextRequest("http://127.0.0.1:3000/api/workflows/runs", {
    headers: {
      host: "127.0.0.1:3000",
      referer: "http://127.0.0.1:3000/workflows",
      "sec-fetch-site": "same-origin",
    },
  });
  expect((await GET(req, context)).status).toBe(202);
  req.headers.set("sec-fetch-site", "cross-site");
  expect((await GET(req, context)).status).toBe(403);
});

test("workflow gateway retains production denial and refuses remote token forwarding", async () => {
  Object.assign(process.env, { NODE_ENV: "production" });
  expect((await POST(request(body), context)).status).toBe(404);
  Object.assign(process.env, { NODE_ENV: "development" });
  process.env.BACKEND_API_URL = "https://example.invalid";
  expect((await POST(request(body), context)).status).toBe(500);
  expect(forwarded).toHaveLength(0);
});

test("workflow origin configuration must remain loopback-only", async () => {
  process.env.EDI_DEV_WORKFLOW_ORIGIN = "http://example.invalid:3000";
  expect((await POST(request(body), context)).status).toBe(500);
  expect(forwarded).toHaveLength(0);
});
