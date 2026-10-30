import { test, expect } from "@playwright/test";
import { ApiError, request } from "../src/lib/api";

test("CSRF service errors retain backend status and detail before any mutation", async () => {
  const original = globalThis.fetch;
  const urls: string[] = [];
  globalThis.fetch = async url => {
    urls.push(String(url));
    return Response.json({detail: "Configure HTTPS application origins."}, {status: 503});
  };
  try {
    await expect(request("/auth/login", {method: "POST"})).rejects.toMatchObject({name: "ApiError", status: 503, message: "Configure HTTPS application origins."});
    expect(urls).toEqual(["/api/bridge/auth/csrf"]);
  } finally {
    globalThis.fetch = original;
  }
});

test("network failures retain the proxy connectivity message", async () => {
  const original = globalThis.fetch;
  globalThis.fetch = async () => {throw new TypeError("synthetic offline");};
  try {
    await expect(request("/auth/login", {method: "POST"})).rejects.toBeInstanceOf(ApiError);
    await expect(request("/auth/login", {method: "POST"})).rejects.toMatchObject({status: 0, message: "Cannot reach the frontend API proxy. Is Next.js running?"});
  } finally {
    globalThis.fetch = original;
  }
});

test("malformed successful CSRF response cannot submit a mutation", async () => {
  const original = globalThis.fetch;
  let calls = 0;
  globalThis.fetch = async () => {calls++; return Response.json({csrf_token: 123});};
  try {
    await expect(request("/auth/login", {method: "POST"})).rejects.toMatchObject({message: "The session service returned an invalid response."});
    expect(calls).toBe(1);
  } finally {
    globalThis.fetch = original;
  }
});
