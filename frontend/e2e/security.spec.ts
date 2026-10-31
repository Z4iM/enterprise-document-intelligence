import { test, expect, type Page } from "@playwright/test";

async function login(page: Page, role: string) {
  await page.goto("/documents");
  await page.getByLabel("Email", {exact: true}).fill(`${role}@synthetic.test`);
  await page.getByLabel("Password", {exact: true}).fill("synthetic-browser-password");
  await page.getByRole("button", {name: "Sign in", exact: true}).click();
  await expect(page.getByRole("button", {name: "Open user profile", exact: true})).toBeVisible({timeout: 15000});
}

async function signOut(page: Page) {
  await page.getByRole("button", {name: "Open user profile", exact: true}).click();
  await page.getByRole("button", {name: "Sign out", exact: true}).click();
}

for (const role of ["employee", "reviewer"]) {
  test(`${role} profile restricts name editing to administrators`, async ({page}) => {
    await login(page, role);
    await page.getByRole("button", {name: "Open user profile", exact: true}).click();
    const profile = page.getByRole("region", {name: "Your profile", exact: true});
    await expect(profile.getByText("Your name is managed by an administrator.", {exact: true})).toBeVisible();
    await expect(profile.getByLabel("Your name", {exact: true})).toHaveCount(0);
    await expect(profile.getByRole("button", {name: "Save name", exact: true})).toHaveCount(0);
    await expect(profile.getByRole("button", {name: "Change password", exact: true})).toBeVisible();
    await expect(profile.getByText("Documents uploaded", {exact: true})).toBeVisible();
  });
}

test("real cookie bridge: upload, reviewer correction, rule approval, evidence and logout", async ({page}) => {
  await login(page, "employee");
  await page.goto("/upload");
  await page.getByLabel("Choose document").setInputFiles({name: "browser-receipt.txt", mimeType: "text/plain", buffer: Buffer.from("Receipt\nMerchant: Synthetic Cafe\nDate: 10/30/2026\nTotal: $175.00\nPayment: cash")});
  const uploadResponse = page.waitForResponse(response => response.url().endsWith("/api/bridge/documents/upload") && response.request().method() === "POST");
  await page.getByRole("button", {name: "Upload & analyze document", exact: true}).click();
  const uploaded = await (await uploadResponse).json() as {document_id: string};
  expect(uploaded.document_id).toBeTruthy();
  await expect(page.getByText("Document uploaded; processing continues automatically", {exact: true})).toBeVisible();
  await expect.poll(async () => (await (await page.request.get(`/api/bridge/documents/${uploaded.document_id}/processing`)).json()).state, {timeout: 45000}).toBe("completed");
  await signOut(page);
  await expect(page.getByRole("heading", {name: "Sign in to your workspace"})).toBeVisible();

  await login(page, "reviewer");
  await page.goto(`/reviews?document=${uploaded.document_id}`);
  await page.getByRole("button", {name: /^corrected$/i}).click();
  await page.getByLabel("Corrected fields").fill('{"merchant":"Synthetic Cafe","total":"$175.00","expense_category":"meal"}');
  const reviewResponse = page.waitForResponse(response => response.url().endsWith(`/documents/${uploaded.document_id}/review`) && response.request().method() === "POST");
  await page.getByRole("button", {name: "Save review decision"}).click();
  expect((await reviewResponse).status()).toBe(200);
  await page.goto("/policies");
  await page.getByRole("button", {name: "Approve rule", exact: true}).click();
  await expect(page.getByRole("button", {name: "Approve rule", exact: true})).toHaveCount(0);
  const [originalPolicy] = await Promise.all([
    page.waitForEvent("download"),
    page.getByRole("link", {name: "Download original policy", exact: true}).click(),
  ]);
  expect(originalPolicy.suggestedFilename()).toBe("synthetic_policy.docx");
  await signOut(page);
  await expect(page.getByRole("heading", {name: "Sign in to your workspace"})).toBeVisible();

  await login(page, "employee");
  await page.goto(`/documents/${uploaded.document_id}`);
  await page.getByLabel("Organization policy").selectOption("synthetic-policy");
  await page.getByRole("button", {name: "Evaluate approved rules"}).click();
  await expect(page.getByText("Policy evidence", {exact: true})).toBeVisible();
  await expect(page.locator("blockquote").filter({hasText: "Meals above $100 require manager approval."})).toBeVisible();
  await page.screenshot({path: test.info().outputPath("policy-evidence.png"), fullPage: true});
  await page.getByRole("button", {name: "Review history", exact: true}).click();
  await expect(page.getByText("Synthetic Reviewer", {exact: true})).toBeVisible();
  await signOut(page);
  await expect(page.getByRole("heading", {name: "Sign in to your workspace"})).toBeVisible();
  expect((await page.request.get("/api/bridge/documents")).status()).toBe(401);
});

test("administration creates only local organization accounts and survives reload", async ({page}) => {
  await login(page, "admin");
  await page.goto("/users");
  await page.getByLabel("New user name").fill("New Browser User");
  await page.getByLabel("New user email").fill("new-browser@synthetic.test");
  await page.getByLabel("Initial password").fill("synthetic-created-password");
  await page.getByRole("button", {name: "Create account", exact: true}).click();
  await expect(page.getByText("Account created.", {exact: true})).toBeVisible();
  await page.reload();
  await expect(page.getByText("new-browser@synthetic.test", {exact: true})).toBeVisible();
  await signOut(page);
  await expect(page.getByRole("heading", {name: "Sign in to your workspace"})).toBeVisible();
});


test("automatic policy rules, confirmed bulk approval, profile stats and password rotation", async ({page}) => {
  await login(page, "admin");
  await page.goto("/policies");
  await page.getByLabel("Policy file").setInputFiles({name: "automatic-policy.txt", mimeType: "text/plain", buffer: Buffer.from("Meals above $100 require manager approval.\nFor all expenses of $25 or more, receipts are required.")});
  const extractionResponse = page.waitForResponse(response => response.url().endsWith("/api/bridge/policies/upload") && response.request().method() === "POST", {timeout: 50000});
  await page.getByRole("button", {name: "Upload policy", exact: true}).click();
  const extracted = await extractionResponse;
  expect(extracted.status()).toBe(202);
  const policyUpload = await extracted.json();
  expect(policyUpload.rule_extraction.status).toBe("queued");
  await expect.poll(async () => (await (await page.request.get(`/api/bridge/policies/${policyUpload.policy_id}/processing`)).json()).state, {timeout: 45000}).toBe("completed");
  await expect(page.getByText("2 verified rules awaiting your approval", {exact: true})).toBeVisible();
  await expect(page.getByLabel("Source chunk index")).toHaveCount(0);
  await page.getByRole("button", {name: "Approve all verified rules", exact: true}).click();
  await page.getByRole("button", {name: "Confirm approval of 2 rules", exact: true}).click();
  await expect(page.getByText("All selected rules were approved.", {exact: true})).toBeVisible();
  await expect(page.getByText("Reviewer: Synthetic Admin", {exact: true})).toHaveCount(2);
  await page.getByRole("button", {name: "Open user profile", exact: true}).click();
  await page.getByLabel("Your name", {exact: true}).fill("Updated Admin");
  await page.getByRole("button", {name: "Save name", exact: true}).click();
  await expect(page.getByText("Name updated.", {exact: true})).toBeVisible();
  await expect(page.getByRole("heading", {name: "Updated Admin", exact: true})).toBeVisible();
  await expect(page.getByText("Active users in organization", {exact: true})).toBeVisible();
  await expect(page.getByText("Rules approved", {exact: true})).toBeVisible();
  await page.screenshot({path: test.info().outputPath("profile-policy-flow.png"), fullPage: true});
  await page.getByRole("button", {name: "Change password", exact: true}).click();
  await page.getByLabel("Current password", {exact: true}).fill("synthetic-browser-password");
  await page.getByLabel("New password", {exact: true}).fill("synthetic-rotated-password");
  await page.getByLabel("Confirm new password", {exact: true}).fill("synthetic-rotated-password");
  await page.getByRole("button", {name: "Update password", exact: true}).click();
  await expect(page.getByText("Password changed. Other sessions have been signed out.", {exact: true})).toBeVisible();
  await page.getByRole("button", {name: "Sign out", exact: true}).click();
  await page.getByLabel("Email", {exact: true}).fill("admin@synthetic.test");
  await page.getByLabel("Password", {exact: true}).fill("synthetic-rotated-password");
  await page.getByRole("button", {name: "Sign in", exact: true}).click();
  await expect(page.getByRole("button", {name: "Open user profile", exact: true})).toBeVisible({timeout: 15000});
});


test("production investigation explains availability and retains gateway denial", async ({page}) => {
  await login(page, "employee");
  let submitted = false;
  page.on("request", request => {if (request.url().endsWith("/api/agent/investigate") && request.method() === "POST") submitted = true;});
  await page.goto("/investigate");
  await expect(page.getByRole("heading", {name: "AI investigation unavailable", exact: true})).toBeVisible();
  await expect(page.getByText("AI investigation currently requires local development mode. It is disabled in production builds.", {exact: true})).toBeVisible();
  await expect(page.getByRole("button", {name: "Run investigation"})).toBeDisabled();
  await expect(page.getByLabel("Your question", {exact: true})).toBeDisabled();
  await expect(page.getByRole("heading", {name: "Ready for investigation", exact: true})).toHaveCount(0);
  expect(submitted).toBe(false);
  const response = await page.request.post("/api/agent/investigate", {data: {question: "Synthetic question"}});
  expect(response.status()).toBe(404);
});

test("Arabic policy search, exact evidence and reviewer removal preserve original", async ({page}) => {
  await login(page, "reviewer");
  await page.goto("/policies");
  const text = "تتطلب مصروفات الوجبات التي تتجاوز مائة دولار موافقة المدير.";
  await page.getByLabel("Policy file").setInputFiles({name: "arabic-search.txt", mimeType: "text/plain", buffer: Buffer.from(text)});
  const uploaded = page.waitForResponse(response => response.url().endsWith("/api/bridge/policies/upload") && response.request().method() === "POST");
  await page.getByRole("button", {name: "Upload policy", exact: true}).click();
  const policy = (await (await uploaded).json()).policy_id as string;
  await expect.poll(async () => (await (await page.request.get(`/api/bridge/policies/${policy}/index`)).json()).state, {timeout: 45000}).toBe("ready");
  const search = page.getByRole("region", {name: "Search policy evidence"});
  await search.getByLabel("Policy evidence query").fill("موافقة المدير للوجبات");
  await search.getByRole("button", {name: "Search", exact: true}).click();
  await expect(search.locator("blockquote")).toHaveText(text);
  await expect(search.getByText(/source passages · keyword retrieval/)).toBeVisible();
  await search.getByRole("button", {name: "Remove from search", exact: true}).click();
  await search.getByRole("button", {name: "Confirm removal from search", exact: true}).click();
  await expect(search.getByText("This policy is excluded from search.", {exact: true})).toBeVisible();
  expect((await page.request.get(`/api/bridge/policies/${policy}/original`)).status()).toBe(200);
});
