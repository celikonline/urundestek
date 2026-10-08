import { test, expect } from "@playwright/test";
import fs from "node:fs";
import path from "node:path";

test("rich message with a file and clipboard screenshot survives reload", async ({
  page,
  context,
}) => {
  await context.grantPermissions(["clipboard-read", "clipboard-write"]);
  await page.goto("/");
  await page.getByRole("button", { name: /Müşteri alanı/ }).click();
  await page.getByRole("button", { name: "Yeni talep", exact: true }).click();
  const subject = `Dosyalı mesaj ${Date.now()}`;
  await page.getByLabel("Konu", { exact: true }).fill(subject);
  await page
    .getByLabel("Açıklama", { exact: true })
    .fill("Ekran görüntüsü ile sorun bildiriyorum.");
  await page.getByRole("button", { name: "Talebi oluştur" }).click();
  await expect(
    page.getByRole("heading", { name: subject, exact: true, level: 2 }),
  ).toBeVisible();
  await expect(page.locator('.status-track [aria-current="step"]')).toHaveCount(
    1,
  );
  expect(
    await page
      .locator(".status-track .current .status-step-label")
      .evaluate((el) => getComputedStyle(el).boxShadow),
  ).not.toBe("none");
  const editor = page.getByRole("textbox", { name: "Mesajınız" });
  await editor.fill("Biçimli açıklama ve ekran görüntüsü");
  await editor.press("Control+a");
  await page.getByRole("button", { name: "Kalın", exact: true }).click();
  await expect(editor.locator("strong")).toContainText("Biçimli açıklama");
  await page
    .locator('input[type="file"]')
    .setInputFiles({
      name: "hata-detayi.txt",
      mimeType: "text/plain",
      buffer: Buffer.from("Hata kodu: RAPOR-42"),
    });
  const image = fs
    .readFileSync(path.join(process.cwd(), "tests/fixtures/clipboard.png"))
    .toString("base64");
  await page.evaluate(async (base64) => {
    const blob = await (await fetch(`data:image/png;base64,${base64}`)).blob();
    await navigator.clipboard.write([new ClipboardItem({ "image/png": blob })]);
  }, image);
  await editor.click();
  await editor.press("Control+v");
  await expect(page.locator(".draft-file")).toHaveCount(2);
  await expect(page.locator(".draft-file img")).toBeVisible();
  await page.screenshot({
    path: "test-results/editor-with-clipboard.png",
    fullPage: true,
    animations: "disabled",
  });
  await page.getByRole("button", { name: "Mesajı gönder" }).click();
  await expect(page.locator(".message-files .message-file")).toHaveCount(2);
  await page.reload();
  await expect(page.locator(".rich-message strong")).toContainText(
    "Biçimli açıklama",
  );
  await expect(page.locator(".message-files img")).toBeVisible();
  const download = page
    .locator(".message-file")
    .filter({ hasText: "hata-detayi.txt" });
  const response = await page.request.get(
    (await download.getAttribute("href"))!,
  );
  expect(response.status()).toBe(200);
  expect(await response.text()).toBe("Hata kodu: RAPOR-42");
  expect(
    await editor.evaluate((el) => parseFloat(getComputedStyle(el).fontSize)),
  ).toBeGreaterThanOrEqual(16);
  expect(
    await page
      .locator(".rich-message p")
      .first()
      .evaluate((el) => parseFloat(getComputedStyle(el).fontSize)),
  ).toBeGreaterThanOrEqual(16);
  await page.setViewportSize({ width: 375, height: 812 });
  await expect(editor).toBeVisible();
  expect(
    await page.evaluate(
      () => document.documentElement.scrollWidth <= innerWidth,
    ),
  ).toBeTruthy();
  await page.screenshot({
    path: "test-results/messages-mobile.png",
    fullPage: true,
    animations: "disabled",
  });
});

test("public and private drafts stay separate; drag-drop and attachment-only message", async ({
  page,
}) => {
  await page.goto("/");
  await page.getByRole("button", { name: /Destek yönetimi/ }).click();
  await page
    .getByRole("textbox", { name: "Mesajınız" })
    .fill("Müşteriye açık taslak");
  await page.getByRole("button", { name: "İç not", exact: true }).click();
  const privateEditor = page.getByRole("textbox", {
    name: "İç not",
    exact: true,
  });
  await expect(privateEditor).toHaveText("");
  await privateEditor.fill("Yalnız ekip için taslak");
  await page
    .getByRole("button", { name: "Müşteriye yanıt", exact: true })
    .click();
  await expect(page.getByRole("textbox", { name: "Mesajınız" })).toHaveText(
    "Müşteriye açık taslak",
  );
  await page.getByRole("button", { name: "İç not", exact: true }).click();
  await expect(privateEditor).toHaveText("Yalnız ekip için taslak");
  await privateEditor.fill("");
  await privateEditor.evaluate((el) => {
    const transfer = new DataTransfer();
    transfer.items.add(
      new File(["İç not eki"], "ekip.txt", { type: "text/plain" }),
    );
    el.dispatchEvent(
      new DragEvent("drop", {
        dataTransfer: transfer,
        bubbles: true,
        cancelable: true,
      }),
    );
  });
  await expect(page.locator(".message-editor:visible .draft-file")).toHaveCount(
    1,
  );
  await page.getByRole("button", { name: "Notu kaydet" }).click();
  await expect(
    page
      .locator(".message.internal .message-file")
      .filter({ hasText: "ekip.txt" }),
  ).toBeVisible();
});
