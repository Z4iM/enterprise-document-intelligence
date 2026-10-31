import { test, expect, type Page } from "@playwright/test";

async function login(page: Page, role: string) {
  await page.goto("/documents");
  await page
    .getByLabel("Email", { exact: true })
    .fill(`${role}@synthetic.test`);
  await page
    .getByLabel("Password", { exact: true })
    .fill("synthetic-browser-password");
  const signedIn = page.waitForResponse(response => response.url().endsWith("/api/bridge/auth/login") && response.request().method() === "POST", {timeout: 15000});
  await page.getByRole("button", { name: "Sign in", exact: true }).click();
  expect((await signedIn).status()).toBe(200);
  await expect(
    page.getByRole("button", { name: "Open user profile" }),
  ).toBeVisible();
}

for (const role of ["employee", "reviewer"]) {
  test(`${role} cannot access operations through UI or API`, async ({
    page,
  }) => {
    await login(page, role);
    await expect(
      page.getByRole("link", { name: "Operations", exact: true }),
    ).toHaveCount(0);
    expect(
      (await page.request.get("/api/bridge/operations/summary")).status(),
    ).toBe(403);
    await page.goto("/operations");
    await expect(
      page.getByText("Operations requires an administrator account.", {
        exact: true,
      }),
    ).toBeVisible();
  });
}

test("admin inspects organization operations and correlated trace without invented cost", async ({
  page,
}) => {
  await login(page, "admin");
  const response = await page.request.get("/api/bridge/documents");
  const reference = response.headers()["x-request-id"];
  expect(reference).toMatch(/^[a-f0-9]{32}$/);
  await page.getByRole("link", { name: "Operations", exact: true }).click();
  await expect(
    page.getByRole("heading", { name: "Operations", exact: true }),
  ).toBeVisible();
  await expect(
    page.getByRole("heading", { name: "Latency and errors", exact: true }),
  ).toBeVisible();
  await expect(
    page
      .getByRole("heading", { name: "Configured cost estimate", exact: true })
      .locator("..")
      .getByText("Unknown", { exact: true }),
  ).toBeVisible();
  await page.getByLabel("Trace reference", { exact: true }).fill(reference);
  await page.getByRole("button", { name: "Find trace", exact: true }).click();
  await expect(
    page.getByRole("heading", { name: "Trace details", exact: true }),
  ).toBeVisible();
  await expect(page.getByRole("heading", {name: "Trace details", exact: true}).locator("..").getByText(/http\.request · ok ·/)).toBeVisible();
  await page.setViewportSize({ width: 390, height: 844 });
  expect(
    await page.evaluate(
      () => document.documentElement.scrollWidth <= window.innerWidth + 1,
    ),
  ).toBe(true);
  await page.screenshot({
    path: test.info().outputPath("operations-mobile.png"),
    fullPage: true,
  });
});
