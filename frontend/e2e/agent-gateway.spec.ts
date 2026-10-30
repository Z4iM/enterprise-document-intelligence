import { test, expect } from "@playwright/test";
import { NextRequest } from "next/server";
import { POST } from "../src/app/api/agent/investigate/route";

const variables = ["NODE_ENV", "EDI_ENABLE_DEV_AGENT_FRONTEND", "EDI_DEV_AGENT_TOKEN", "BACKEND_API_URL"];
let saved: Record<string, string | undefined>;
let originalFetch: typeof fetch;
let forwarded: {url: string; init?: RequestInit}[];

test.beforeEach(() => {
  saved = Object.fromEntries(variables.map(key => [key, process.env[key]]));
  Object.assign(process.env, {NODE_ENV: "development", EDI_ENABLE_DEV_AGENT_FRONTEND: "true", EDI_DEV_AGENT_TOKEN: "synthetic-gateway-token", BACKEND_API_URL: "http://127.0.0.1:8000"});
  originalFetch = globalThis.fetch;
  forwarded = [];
  globalThis.fetch = async (url, init) => {
    forwarded.push({url: String(url), init});
    return Response.json({status: "not_ready", reason: "missing_evidence", tool_trace: []});
  };
});

test.afterEach(() => {
  globalThis.fetch = originalFetch;
  for (const key of variables) {
    if (saved[key] === undefined) delete process.env[key];
    else process.env[key] = saved[key];
  }
});

function request(payload: unknown, headers: Record<string, string> = {}) {
  return new NextRequest("http://127.0.0.1:3000/api/agent/investigate", {
    method: "POST", headers: {host: "127.0.0.1:3000", origin: "http://127.0.0.1:3000", "Content-Type": "application/json", "x-csrf-token": "synthetic-csrf", cookie: "edi_session=synthetic-session", ...headers}, body: JSON.stringify(payload),
  });
}

test("gateway forwards selections, session and CSRF without browser permission grants", async () => {
  const response = await POST(request({question: " Investigate this receipt ", document_id: "selected-doc", policy_id: "selected-policy"}));
  expect(response.status).toBe(200);
  expect(forwarded).toHaveLength(1);
  expect(forwarded[0].url).toBe("http://127.0.0.1:8000/agent/investigate");
  expect(JSON.parse(String(forwarded[0].init?.body))).toEqual({question: "Investigate this receipt", document_id: "selected-doc", policy_id: "selected-policy"});
  const headers = new Headers(forwarded[0].init?.headers);
  expect(headers.get("x-csrf-token")).toBe("synthetic-csrf");
  expect(headers.get("Cookie")).toBe("edi_session=synthetic-session");
  expect(headers.get("x-edi-agent-token")).toBe("synthetic-gateway-token");
  expect(await response.text()).not.toContain("synthetic-gateway-token");
});

for (const [name, payload] of [
  ["permission injection", {question: "Synthetic", allowed_document_ids: ["other-doc"]}],
  ["partial selection", {question: "Synthetic", document_id: "selected-doc"}],
  ["path traversal", {question: "Synthetic", document_id: "../private", policy_id: "selected-policy"}],
  ["role injection", {question: "Synthetic", document_id: "selected-doc", policy_id: "selected-policy", role: "admin"}],
] as const) {
  test(`gateway rejects ${name}`, async () => {
    expect((await POST(request(payload))).status).toBe(422);
    expect(forwarded).toHaveLength(0);
  });
}

test("gateway keeps production denial even when enabled", async () => {
  Object.assign(process.env, {NODE_ENV: "production"});
  expect((await POST(request({question: "Synthetic"}))).status).toBe(404);
  expect(forwarded).toHaveLength(0);
});

test("gateway retains local host and origin restrictions", async () => {
  expect((await POST(request({question: "Synthetic"}, {host: "remote.example"}))).status).toBe(403);
  expect((await POST(request({question: "Synthetic"}, {origin: "https://remote.example"}))).status).toBe(403);
  expect(forwarded).toHaveLength(0);
});

test("gateway never redirects investigation to an external backend", async () => {
  process.env.BACKEND_API_URL = "https://remote.example";
  expect((await POST(request({question: "Synthetic"}))).status).toBe(503);
  expect(forwarded).toHaveLength(0);
});

test("complete gateway and real backend investigation discovers account resources without ID settings", async ({request: api}) => {
  async function login(role: string) {
    const challenge = await (await api.get("http://127.0.0.1:8197/auth/csrf")).json();
    const response = await api.post("http://127.0.0.1:8197/auth/login", {
      data: {email: `${role}@synthetic.test`, password: "synthetic-browser-password"},
      headers: {"x-csrf-token": challenge.csrf_token, origin: "http://127.0.0.1:3197"},
    });
    expect(response.status()).toBe(200);
    return (await response.json()).csrf_token as string;
  }
  const reviewerCsrf = await login("reviewer");
  const headers = {"x-csrf-token": reviewerCsrf, origin: "http://127.0.0.1:3197"};
  const upload = await api.post("http://127.0.0.1:8197/policies/upload", {
    headers, multipart: {file: {name: "gateway-policy.txt", mimeType: "text/plain", buffer: Buffer.from("Gateway integration policy\nMeals above $100 require manager approval.\nFor all expenses of $25 or more, receipts are required.")}},
  });
  expect(upload.status()).toBe(202);
  const policy = await upload.json();
  await expect.poll(async () => (await (await api.get(`http://127.0.0.1:8197/policies/${policy.policy_id}/processing`)).json()).state, {timeout: 45000}).toBe("completed");
  const rules = await (await api.get(`http://127.0.0.1:8197/policies/${policy.policy_id}/rules`)).json();
  const approval = await api.post(`http://127.0.0.1:8197/policies/${policy.policy_id}/rules/approve-all`, {headers, data: {rule_ids: rules.rules.map((r: {id: string}) => r.id)}});
  expect(approval.status()).toBe(200);

  const employeeCsrf = await login("employee");
  const documents = await (await api.get("http://127.0.0.1:8197/documents")).json();
  const policies = await (await api.get("http://127.0.0.1:8197/policies")).json();
  const selectedPolicy = policies.find((p: {filename: string}) => p.filename === "gateway-policy.txt");
  expect(selectedPolicy).toBeTruthy();
  const cookie = (await api.storageState()).cookies.map(c => `${c.name}=${c.value}`).join("; ");
  process.env.BACKEND_API_URL = "http://127.0.0.1:8197";
  process.env.EDI_DEV_AGENT_TOKEN = "synthetic-browser-agent-token";
  globalThis.fetch = originalFetch;
  const response = await POST(request({question: "What actions does this meal receipt require?", document_id: documents[0].document_id, policy_id: selectedPolicy.policy_id}, {cookie, "x-csrf-token": employeeCsrf}));
  expect(response.status).toBe(200);
  const result = await response.json();
  expect(result.status).toBe("ready");
  expect(result.answer.document_id).toBe(documents[0].document_id);
  expect(result.answer.policy_id).toBe(selectedPolicy.policy_id);
  expect(result.answer.full_compliance_certified).toBe(false);
  expect(result.tool_trace.map((step: {tool: string}) => step.tool)).toEqual(["inspect_document", "get_policy_evidence", "evaluate_document_policy"]);
  expect(JSON.stringify(result)).not.toContain("Unverified synthetic draft");
});
