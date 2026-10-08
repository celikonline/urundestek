import { test, expect } from "@playwright/test";

test("help suggestions, draft survives reload, response target and rating after close", async ({
  page,
}) => {
  await page.goto("/");
  await page.getByRole("button", { name: /Müşteri alanı/ }).click();
  await expect(
    page.getByRole("heading", { name: "Birlikte çözelim." }),
  ).toBeVisible();

  // Knowledge base suggestions appear while typing the subject.
  await page.getByRole("button", { name: "Yeni talep", exact: true }).click();
  const subject = `Bordro raporu indiremiyorum ${Date.now()}`;
  await page.getByLabel("Konu", { exact: true }).fill(subject);
  await expect(
    page.getByText("Talep açmadan önce bunlar yardımcı olabilir"),
  ).toBeVisible();
  await page.getByText("Bordro ve raporlar", { exact: true }).click();
  await expect(page.getByText(/Rapor hazırlanıyor/)).toBeVisible();

  // The draft lives in the browser, so a reload keeps subject and description.
  await page
    .getByLabel("Açıklama", { exact: true })
    .fill("Ekim dönemi raporu hazırlanıyor ekranında kalıyor.");
  await page.waitForTimeout(400);
  await page.reload();
  await page.getByRole("button", { name: "Yeni talep", exact: true }).click();
  await expect(page.getByLabel("Konu", { exact: true })).toHaveValue(subject);
  await expect(page.getByLabel("Açıklama", { exact: true })).toContainText(
    "Ekim dönemi raporu",
  );
  await page.getByRole("button", { name: "Talebi oluştur" }).click();
  await expect(
    page.getByRole("heading", { name: subject, exact: true, level: 2 }),
  ).toBeVisible();
  await expect(page.getByText(/tarihine kadar yanıt vereceğiz/)).toBeVisible();

  // After closing, the customer can rate exactly once.
  await page.getByRole("button", { name: "Talebi kapat", exact: true }).click();
  await expect(page.getByText("Bu talep kapatıldı.")).toBeVisible();
  const prompt = page.getByRole("form", { name: "Memnuniyet değerlendirmesi" });
  await expect(prompt).toBeVisible();
  await prompt.getByRole("radio", { name: /4 yıldız/ }).click();
  await prompt.getByLabel("Yorumunuz").fill("Hızlı dönüş, teşekkürler.");
  await prompt.getByRole("button", { name: "Değerlendirmeyi gönder" }).click();
  await expect(page.getByText("4/5 · İyi")).toBeVisible();
  await expect(prompt).toHaveCount(0);

  // Drafts are cleared once the ticket is created.
  await page.getByRole("button", { name: "Yeni talep", exact: true }).click();
  await expect(page.getByLabel("Konu", { exact: true })).toHaveValue("");
});
