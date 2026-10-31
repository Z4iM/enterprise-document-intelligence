import { test, expect, type Page } from "@playwright/test";
import { readFileSync } from "node:fs";
import path from "node:path";

test.skip(
  process.env.EDI_E2E_SHOWCASE !== "true" || process.env.EDI_E2E_WORKFLOW_DEV !== "true",
  "Explicit isolated development gateway run only.",
);
test.setTimeout(120000);
test.use({actionTimeout: 15000});

async function login(page: Page, role: string) {
  await page.goto("/documents");
  await page
    .getByLabel("Email", { exact: true })
    .fill(`${role}@synthetic.test`);
  await page
    .getByLabel("Password", { exact: true })
    .fill("synthetic-browser-password");
  await page.getByRole("button", { name: "Sign in", exact: true }).click();
  await expect(
    page.getByRole("button", { name: "Open user profile" }),
  ).toBeVisible({timeout: 15000});
}
async function logout(page: Page) {
  await page.getByRole("button", { name: "Open user profile" }).click();
  await page.getByRole("button", { name: "Sign out", exact: true }).click();
  await expect(
    page.getByRole("heading", { name: "Sign in to your workspace" }),
  ).toBeVisible();
}

const fixtures = path.resolve(__dirname, "../../docs/demo/fixtures");
for (const scenario of [
  {language: "en", merchant: "Synthetic Harbor Cafe", total: "175.50 USD", category: "meal", marker: "175", question: "What requirements apply to this receipt?", quote: "Meals above $100", note: "Checked the original receipt, amount and reviewed fields."},
  {language: "ar", merchant: "مطعم تجريبي", total: "175.50 EGP", category: "وجبات", marker: "١٧٥", question: "ما المتطلبات اللازمة لهذا الإيصال؟", quote: "مصروفات الوجبات", note: "تم التحقق من الإيصال الأصلي وقيمة المصروف والحقول المراجعة."},
]) {
test(`${scenario.language} empty-sandbox showcase verifies review, evidence, scoped access and operational trace`, async ({
  page,
}) => {
  test.setTimeout(180000);
  await page.setViewportSize({ width: 1440, height: 1100 });
  await login(page, "reviewer");
  await page.goto("/policies");
  await expect(page.getByLabel("Synthetic showcase notice")).toContainText("Scripted model generation");
  if (scenario.language === "en") {
    expect(await (await page.request.get("/api/bridge/documents")).json()).toHaveLength(0);
    expect(await (await page.request.get("/api/bridge/policies")).json()).toHaveLength(0);
  }
  const policyText = readFileSync(path.join(fixtures, `${scenario.language}-policy.txt`), "utf8");
  await page.getByLabel("Policy file").setInputFiles({
    name: `${scenario.language}-showcase-policy.txt`,
    mimeType: "text/plain",
    buffer: Buffer.from(policyText),
  });
  const policyResponse = page.waitForResponse(
    (response) =>
      response.url().endsWith("/api/bridge/policies/upload") &&
      response.request().method() === "POST",
  );
  await page
    .getByRole("button", { name: "Upload policy", exact: true })
    .click();
  const policy = (await (await policyResponse).json()).policy_id as string;
  await expect(
    page.getByRole("button", {
      name: "Approve all verified rules",
      exact: true,
    }),
  ).toBeVisible({ timeout: 45000 });
  await page
    .getByRole("button", { name: "Approve all verified rules", exact: true })
    .click();
  await page
    .getByRole("button", { name: "Confirm approval of 2 rules", exact: true })
    .click();
  await expect(
    page.getByText("All selected rules were approved.", { exact: true }),
  ).toBeVisible();
  const search = page.getByLabel("Search policy evidence", {exact: true});
  await expect(search.getByRole("status").filter({hasText: /index ·/})).toBeVisible({timeout: 45000});
  await search.getByLabel("Policy evidence query", {exact: true}).fill(scenario.quote);
  await search.getByRole("button", {name: "Search", exact: true}).click();
  await expect(search.locator("blockquote").filter({hasText: scenario.quote})).toBeVisible();
  expect((await page.request.get((await search.getByRole("link", {name: "Open original policy", exact: true}).getAttribute("href"))!)).status()).toBe(200);
  await page.screenshot({path: test.info().outputPath(`${scenario.language}-policy-review.png`), fullPage: true});
  await logout(page);
  await login(page, "employee");
  await page.goto("/upload");
  await page.screenshot({path: test.info().outputPath(`${scenario.language}-intake.png`), fullPage: true});
  const original = readFileSync(path.join(fixtures, `${scenario.language}-receipt.txt`), "utf8");
  await page.getByLabel("Choose document").setInputFiles({
    name: `${scenario.language}-showcase-receipt.txt`,
    mimeType: "text/plain",
    buffer: Buffer.from(original),
  });
  const uploaded = page.waitForResponse(
    (response) =>
      response.url().endsWith("/api/bridge/documents/upload") &&
      response.request().method() === "POST",
  );
  await page
    .getByRole("button", { name: "Upload & analyze document", exact: true })
    .click();
  const uploadResponse = await uploaded;
  const requestReference = uploadResponse.headers()["x-request-id"];
  expect(requestReference).toMatch(/^[a-f0-9]{32}$/);
  const document = (await uploadResponse.json()).document_id as string;
  await expect
    .poll(
      async () =>
        (
          await (
            await page.request.get(
              `/api/bridge/documents/${document}/processing`,
            )
          ).json()
        ).state,
      { timeout: 45000 },
    )
    .toBe("completed");
  expect(
    (
      await (
        await page.request.get(`/api/bridge/documents/${document}/processing`)
      ).json()
    ).trace_id,
  ).toBe(requestReference);
  await page.goto("/workflows");
  await page.getByLabel("Workflow document").selectOption(document);
  await page.getByLabel("Workflow policy").selectOption(policy);
  const question = scenario.question;
  await page.getByLabel("Workflow question").fill(question);
  await page
    .getByRole("button", { name: "Start workflow", exact: true })
    .click();
  await expect(
    page
      .getByRole("status")
      .filter({ hasText: /^waiting for document review$/ }),
  ).toBeVisible({ timeout: 30000 });
  await logout(page);
  await login(page, "reviewer");
  await page.goto(`/reviews?document=${document}`);
  await page.getByRole("button", { name: /^corrected$/i }).click();
  await page.getByLabel("Corrected fields").fill(
    JSON.stringify({
      merchant: scenario.merchant,
      total: scenario.total,
      expense_category: scenario.category,
      date: "2026-10-31",
      payment_method: "cash",
    }),
  );
  await page.screenshot({path: test.info().outputPath(`${scenario.language}-review.png`), fullPage: true});
  const savedReview = page.waitForResponse(response => response.url().endsWith(`/api/bridge/documents/${document}/review`) && response.request().method() === "POST");
  await page
    .getByRole("button", { name: "Save review decision", exact: true })
    .click();
  const reviewResponse = await savedReview;
  expect(reviewResponse.status()).toBe(200);
  expect((await reviewResponse.json()).review_status).toBe("corrected");
  await page.goto(`/documents/${document}`);
  await page.getByLabel("Organization policy").selectOption(policy);
  const checklist = page
    .getByRole("heading", { name: "Documentation requirements", exact: true })
    .locator("..");
  await expect(
    checklist.getByRole("checkbox", { name: new RegExp(`${scenario.language}-showcase-receipt\\.txt`) }),
  ).toBeChecked();
  const originalLink = checklist
    .getByRole("checkbox", { name: new RegExp(`${scenario.language}-showcase-receipt\\.txt`) })
    .locator("..")
    .locator("..")
    .getByRole("link", { name: "Open original", exact: true });
  const downloadedOriginal = await page.request.get(
    (await originalLink.getAttribute("href"))!,
  );
  expect(downloadedOriginal.status()).toBe(200);
  expect(await downloadedOriginal.text()).toContain(scenario.marker);
  await checklist
    .getByRole("textbox")
    .fill(scenario.note);
  await checklist
    .getByRole("button", { name: "Confirm documentation review", exact: true })
    .click();
  await expect(
    checklist.getByText(
      "Supporting documentation was explicitly reviewed. Expense approval remains separate.",
      { exact: true },
    ),
  ).toBeVisible();
  await logout(page);
  await login(page, "employee");
  await page.goto("/workflows");
  await page.getByRole("button", { name: question, exact: false }).click();
  await page
    .getByRole("button", {
      name: "Recheck recorded reviews and resume",
      exact: true,
    })
    .click();
  await expect(
    page.getByRole("status").filter({ hasText: /^completed$/ }),
  ).toBeVisible({ timeout: 30000 });
  await expect(page.getByRole("button", {name: question, exact: false})).toContainText("completed");
  await expect(
    page.getByRole("heading", {
      name: "Approved-rule outcome: requires approval",
      exact: true,
    }),
  ).toBeVisible();
  await expect(
    page.getByRole("heading", { name: "document specialist", exact: true }),
  ).toBeVisible();
  await expect(
    page.getByRole("heading", { name: "policy specialist", exact: true }),
  ).toBeVisible();
  await expect(
    page.locator("blockquote").filter({ hasText: scenario.quote }),
  ).toBeVisible();
  expect(
    (
      await page.request.get(`/api/bridge/documents/${document}/original`)
    ).status(),
  ).toBe(200);
  await page.screenshot({
    path: test.info().outputPath(`${scenario.language}-workflow-desktop.png`),
    fullPage: true,
  });
  await page.setViewportSize({ width: 390, height: 844 });
  expect(
    await page.evaluate(
      () =>
        globalThis.document.documentElement.scrollWidth <=
        window.innerWidth + 1,
    ),
  ).toBe(true);
  await page.screenshot({
    path: test.info().outputPath(`${scenario.language}-workflow-mobile.png`),
    fullPage: true,
  });
  await page.setViewportSize({width: 1440, height: 1100});
  await page.goto(`/documents/${document}`);
  await page.getByRole("button", {name: "Audit trail", exact: true}).click();
  await expect(page.getByText("Human Review", {exact: true})).toBeVisible();
  await page.screenshot({path: test.info().outputPath(`${scenario.language}-audit.png`), fullPage: true});
  expect((await page.request.get("/api/bridge/operations/summary")).status()).toBe(403);
  await logout(page);
  await login(page, "colleague");
  expect(await (await page.request.get("/api/bridge/documents")).json()).toHaveLength(0);
  expect((await page.request.get(`/api/bridge/documents/${document}`)).status()).toBe(404);
  expect((await page.request.get(`/api/bridge/documents/${document}/original`)).status()).toBe(404);
  await logout(page);
  await login(page, "admin");
  await page.setViewportSize({width: 1680, height: 1100});
  await page.goto("/operations");
  await page.getByLabel("Trace reference", {exact: true}).fill(requestReference);
  await page.getByRole("button", {name: "Find trace", exact: true}).click();
  await expect(page.getByRole("heading", {name: "Trace details", exact: true})).toBeVisible();
  await expect(page.getByRole("heading", {name: "Configured cost estimate", exact: true}).locator("..").getByText("Unknown", {exact: true})).toBeVisible();
  await page.screenshot({path: test.info().outputPath(`${scenario.language}-operations.png`), fullPage: true});
});
}
