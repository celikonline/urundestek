import { test, expect } from "@playwright/test";
import fs from "node:fs";
import path from "node:path";

test("failed creation keeps the pasted draft visible when Escape is pressed during upload", async ({
  page,
}) => {
  await page.goto("/");
  await page.getByRole("button", { name: /Müşteri alanı/ }).click();
  await page.getByRole("button", { name: "Yeni talep", exact: true }).click();
  const dialog = page.getByRole("dialog");
  const subject = `Tekrar gönderilen görsel ${Date.now()}`;
  await page.getByLabel("Konu", { exact: true }).fill(subject);
  await dialog
    .locator('input[type="file"]')
    .setInputFiles(path.join(process.cwd(), "tests/fixtures/clipboard.png"));
  let release!: () => void;
  const wait = new Promise<void>((resolve) => {
    release = resolve;
  });
  await page.route("**/api/v1/tickets/with-files", async (route) => {
    await wait;
    await route.fulfill({
      status: 503,
      contentType: "application/json",
      body: JSON.stringify({ detail: "Geçici hata. Tekrar deneyin." }),
    });
  });
  await dialog
    .getByRole("button", { name: "Talebi oluştur", exact: true })
    .click();
  await expect(
    dialog.getByRole("button", { name: "Oluşturuluyor…", exact: true }),
  ).toBeDisabled();
  await page.keyboard.press("Escape");
  await expect(dialog).toBeVisible();
  release();
  await expect(dialog.getByRole("alert")).toHaveText(
    "Geçici hata. Tekrar deneyin.",
  );
  await expect(dialog.locator(".draft-file img")).toBeVisible();
  await expect(page.getByLabel("Konu", { exact: true })).toHaveValue(subject);
  await page.unroute("**/api/v1/tickets/with-files");
  await dialog
    .getByRole("button", { name: "Talebi oluştur", exact: true })
    .click();
  await expect(
    page.getByRole("heading", { name: subject, exact: true, level: 2 }),
  ).toBeVisible();
  await expect(page.locator(".message-file img")).toBeVisible();
});

test("new request accepts a pasted screenshot and keeps the opening attachment after reload", async ({
  page,
  context,
}) => {
  await context.grantPermissions(["clipboard-read", "clipboard-write"]);
  await page.goto("/");
  await page.getByRole("button", { name: /Müşteri alanı/ }).click();
  await page.getByRole("button", { name: "Yeni talep", exact: true }).click();
  const dialog = page.getByRole("dialog");
  const subject = `İlk talepte ekran görüntüsü ${Date.now()}`;
  await page.getByLabel("Konu", { exact: true }).fill(subject);
  const description = dialog.getByRole("textbox", {
    name: "Açıklama",
    exact: true,
  });
  const image = fs
    .readFileSync(path.join(process.cwd(), "tests/fixtures/clipboard.png"))
    .toString("base64");
  await page.evaluate(async (base64) => {
    const blob = await (await fetch(`data:image/png;base64,${base64}`)).blob();
    await navigator.clipboard.write([new ClipboardItem({ "image/png": blob })]);
  }, image);
  await description.click();
  await description.press("Control+v");
  await expect(dialog.locator(".draft-file img")).toBeVisible();
  await page.screenshot({
    path: "test-results/new-ticket-clipboard.png",
    animations: "disabled",
  });
  await page.setViewportSize({ width: 375, height: 812 });
  expect(
    await page.evaluate(
      () => document.documentElement.scrollWidth <= innerWidth,
    ),
  ).toBeTruthy();
  await page.screenshot({
    path: "test-results/new-ticket-clipboard-mobile.png",
    animations: "disabled",
  });
  await page
    .getByRole("button", { name: "Talebi oluştur", exact: true })
    .click();
  await expect(
    page.getByRole("heading", { name: subject, exact: true, level: 2 }),
  ).toBeVisible();
  await expect(page.locator(".message-file img")).toBeVisible();
  await page.reload();
  await expect(page.locator(".message-file img")).toBeVisible();
  const href = await page.locator(".message-file").first().getAttribute("href");
  const response = await page.request.get(href!);
  expect(response.status()).toBe(200);
  expect(response.headers()["content-type"]).toBe("image/png");
});
