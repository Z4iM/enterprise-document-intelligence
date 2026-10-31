import { test, expect, type Page } from "@playwright/test";

test.skip(
  process.env.EDI_E2E_WORKFLOW_DEV !== "true",
  "Explicit isolated development gateway run only.",
);
test.setTimeout(120000);

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
  ).toBeVisible();
}
async function logout(page: Page) {
  await page.getByRole("button", { name: "Open user profile" }).click();
  await page.getByRole("button", { name: "Sign out", exact: true }).click();
  await expect(
    page.getByRole("heading", { name: "Sign in to your workspace" }),
  ).toBeVisible();
}

test("Arabic specialist workflow pauses, accepts reviewed existing receipt, resumes with cited requirements", async ({
  page,
}) => {
  test.setTimeout(180000);
  await page.setViewportSize({ width: 1440, height: 1100 });
  await login(page, "reviewer");
  await page.goto("/policies");
  const policyText =
    "مصروفات الوجبات التي تتجاوز ١٠٠ جنيه مصري تتطلب موافقة المدير.\nلجميع المصروفات التي لا تقل عن ٢٥ جنيه مصري، الإيصالات مطلوبة.";
  await page.getByLabel("Policy file").setInputFiles({
    name: "arabic-specialist-policy.txt",
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
  await logout(page);
  await login(page, "employee");
  await page.goto("/upload");
  const original =
    "إيصال\nالتاجر: مطعم تجريبي\nالتاريخ: ٢٠٢٦-١٠-٣٠\nالإجمالي: ١٧٥٫٥٠ جنيه مصري\nطريقة الدفع: نقدا\nالفئة: وجبات";
  await page.getByLabel("Choose document").setInputFiles({
    name: "arabic-specialist-receipt.txt",
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
  const question = "ما المتطلبات اللازمة لهذا الإيصال؟";
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
      merchant: "مطعم تجريبي",
      total: "175.50 EGP",
      expense_category: "وجبات",
      date: "2026-10-30",
      payment_method: "cash",
    }),
  );
  const savedReview = page.waitForResponse(response => response.url().endsWith(`/api/bridge/documents/${document}/review`) && response.request().method() === "POST");
  await page
    .getByRole("button", { name: "Save review decision", exact: true })
    .click();
  expect((await savedReview).status()).toBe(200);
  await page.goto(`/documents/${document}`);
  await page.getByLabel("Organization policy").selectOption(policy);
  const checklist = page
    .getByRole("heading", { name: "Documentation requirements", exact: true })
    .locator("..");
  await expect(
    checklist.getByRole("checkbox", { name: /arabic-specialist-receipt\.txt/ }),
  ).toBeChecked();
  const originalLink = checklist
    .getByRole("checkbox", { name: /arabic-specialist-receipt\.txt/ })
    .locator("..")
    .locator("..")
    .getByRole("link", { name: "Open original", exact: true });
  const downloadedOriginal = await page.request.get(
    (await originalLink.getAttribute("href"))!,
  );
  expect(downloadedOriginal.status()).toBe(200);
  expect(await downloadedOriginal.text()).toContain("١٧٥");
  await checklist
    .getByRole("textbox")
    .fill("تم التحقق من الإيصال الأصلي وقيمة المصروف والحقول المراجعة.");
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
  await page.getByRole("button", { name: new RegExp(question) }).click();
  await page
    .getByRole("button", {
      name: "Recheck recorded reviews and resume",
      exact: true,
    })
    .click();
  await expect(
    page.getByRole("status").filter({ hasText: /^completed$/ }),
  ).toBeVisible({ timeout: 30000 });
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
    page.locator("blockquote").filter({ hasText: "مصروفات الوجبات" }),
  ).toBeVisible();
  expect(
    (
      await page.request.get(`/api/bridge/documents/${document}/original`)
    ).status(),
  ).toBe(200);
  await page.screenshot({
    path: test.info().outputPath("arabic-specialist-workflow.png"),
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
    path: test.info().outputPath("arabic-specialist-workflow-mobile.png"),
    fullPage: true,
  });
});


test("stale policy evidence shows historical approval warning and actionable investigation failure", async ({page}) => {
  await login(page, "admin");
  await page.route("**/api/bridge/policies/synthetic-policy/rules", async route => {
    const response = await route.fetch();
    const data = await response.json();
    data.invalid_approved_rule_count = 1;
    data.rules[0].approval_status = "approved";
    data.rules[0].approved_by_name = "Synthetic Reviewer";
    data.rules[0].current_validation = {status: "invalid", reason: "policy_wording_unsupported"};
    await route.fulfill({response, json: data});
  });
  await page.goto("/policies");
  await page.getByRole("button", {name: "synthetic_policy.docx", exact: true}).click();
  await expect(page.getByText("Previously approved policy evidence needs review", {exact: true})).toBeVisible();
  await expect(page.getByText(/^previously approved$/i)).toBeVisible();
  await expect(page.getByText(/Retrying extraction on this copy preserves existing approvals/)).toBeVisible();
  await expect(page.getByRole("alert").filter({hasText: /negation, exceptions or discretionary wording/})).toBeVisible();
  await page.screenshot({path: test.info().outputPath("stale-policy-warning.png"), fullPage: true});
  await page.route("**/api/agent/investigate", route => route.fulfill({json: {
    status: "not_ready", reason: "policy_wording_unsupported",
    tool_trace: [{tool: "get_policy_evidence", status: "needs_review"}],
  }}));
  await page.goto("/investigate");
  await page.getByLabel("Your question", {exact: true}).fill("What requirements apply to this synthetic receipt?");
  await page.getByRole("button", {name: "Run investigation", exact: true}).click();
  await expect(page.getByRole("heading", {name: "Verified decision unavailable", exact: true})).toBeVisible();
  await expect(page.getByText(/A previously approved rule fails current verification because/)).toBeVisible();
  await expect(page.getByRole("link", {name: "Review policy evidence", exact: true})).toHaveAttribute("href", "/policies");
  await expect(page.getByRole("link", {name: "Review document fields", exact: true})).toHaveAttribute("href", "/reviews");
  await page.screenshot({path: test.info().outputPath("investigation-blocker-guidance.png"), fullPage: true});
});
