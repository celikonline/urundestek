import { test, expect } from "@playwright/test";

test("customer opens request, agent replies privately and publicly, customer reminds and closes", async ({
  page,
  browser,
}) => {
  await page.goto("/");
  await page.getByRole("button", { name: /Müşteri alanı/ }).click();
  await expect(
    page.getByRole("heading", { name: "Birlikte çözelim." }),
  ).toBeVisible();
  await page.getByRole("button", { name: "Yeni talep", exact: true }).click();
  const subject = `Tarayıcı doğrulaması ${Date.now()}`;
  await page.getByLabel("Konu", { exact: true }).fill(subject);
  await page
    .getByLabel("Açıklama", { exact: true })
    .fill("Bordro raporunu indirmek için destek istiyorum.");
  await page.getByRole("button", { name: "Talebi oluştur" }).click();
  await expect(
    page.getByRole("heading", { name: subject, exact: true, level: 2 }),
  ).toBeVisible();
  const id = new URL(page.url()).searchParams.get("talep");
  const staffContext = await browser.newContext();
  const staff = await staffContext.newPage();
  await staff.goto("/");
  await staff.getByRole("button", { name: /Destek yönetimi/ }).click();
  await staff.getByRole("textbox", { name: "Taleplerde ara" }).fill(subject);
  await staff.getByRole("button").filter({ hasText: subject }).click();
  await staff.getByRole("button", { name: "İç not", exact: true }).click();
  await staff
    .getByRole("textbox", { name: "İç not", exact: true })
    .fill("Gizli teknik inceleme notu");
  await staff.getByRole("button", { name: "Notu kaydet" }).click();
  await expect(
    staff.getByText("Gizli teknik inceleme notu", { exact: true }),
  ).toBeVisible();
  await staff
    .getByRole("button", { name: "Müşteriye yanıt", exact: true })
    .click();
  await staff
    .getByRole("textbox", { name: "Mesajınız" })
    .fill("Rapor düzenlendi. Tekrar deneyebilirsiniz.");
  await staff.getByRole("button", { name: "Mesajı gönder" }).click();
  await expect(
    staff.getByText("Rapor düzenlendi. Tekrar deneyebilirsiniz.", {
      exact: true,
    }),
  ).toBeVisible();
  await page.reload();
  await expect(
    page.getByText("Rapor düzenlendi. Tekrar deneyebilirsiniz.", {
      exact: true,
    }),
  ).toBeVisible();
  await expect(
    page.getByText("Gizli teknik inceleme notu", { exact: true }),
  ).toHaveCount(0);
  await page
    .getByRole("button", { name: "Hatırlatma oluştur", exact: true })
    .click();
  await page.getByRole("button", { name: "Hatırlatmayı kaydet" }).click();
  await page
    .getByRole("button", { name: "Hatırlatmalarım", exact: true })
    .click();
  await expect(
    page.getByText("Talebin güncel durumunu kontrol et", { exact: true }),
  ).toBeVisible();
  await page.getByRole("button").filter({ hasText: subject }).click();
  await page.getByRole("button", { name: "Talebi kapat", exact: true }).click();
  await expect(
    page.getByText("Bu talep kapatıldı.", { exact: true }),
  ).toBeVisible();
  await page.getByRole("button", { name: "Yeniden aç", exact: true }).click();
  await expect(page.getByRole("textbox", { name: "Mesajınız" })).toBeVisible();
  await page.evaluate(() => window.scrollTo(0, 0));
  await page.screenshot({
    path: "test-results/customer-desktop.png",
    fullPage: true,
    animations: "disabled",
  });
  await page.setViewportSize({ width: 375, height: 812 });
  await expect
    .poll(async () =>
      page
        .locator(".sidebar")
        .evaluate((el) => el.getBoundingClientRect().right),
    )
    .toBeLessThanOrEqual(0);
  await expect(
    page.getByRole("heading", { name: subject, exact: true, level: 2 }),
  ).toBeVisible();
  expect(
    await page.evaluate(
      () => document.documentElement.scrollWidth <= innerWidth,
    ),
  ).toBeTruthy();
  await page.screenshot({
    path: "test-results/customer-mobile.png",
    fullPage: true,
    animations: "disabled",
  });
  await page.getByRole("button", { name: "Talep listesine dön" }).click();
  await expect(
    page.getByRole("heading", { name: "Taleplerim", exact: false }),
  ).toBeVisible();
  expect(
    await page.evaluate(
      () => document.documentElement.scrollWidth <= innerWidth,
    ),
  ).toBeTruthy();
  const otherContext = await browser.newContext();
  const other = await otherContext.newPage();
  await other.goto("/");
  await other.getByText("Diğer demo hesapları").click();
  await other.getByRole("button", { name: "Nova Lojistik müşterisi" }).click();
  await expect(other.getByRole("heading", { name: "Birlikte çözelim." })).toBeVisible();
  const denied = await other.request.get(`/api/v1/tickets/${id}`);
  expect(denied.status()).toBe(404);
  await staff.screenshot({
    path: "test-results/admin-desktop.png",
    fullPage: true,
    animations: "disabled",
  });
  await otherContext.close();
  await staffContext.close();
});

test("customer filters and keyboard-accessible new-request dialog", async ({
  page,
}) => {
  await page.goto("/");
  await page.getByRole("button", { name: /Müşteri alanı/ }).click();
  await page
    .getByRole("textbox", { name: "Taleplerde ara" })
    .fill("Eşleşmeyen talep zzz");
  await expect(
    page.getByRole("heading", { name: "Burada henüz talep yok" }),
  ).toBeVisible();
  await page.getByRole("button", { name: "Yeni talep", exact: true }).click();
  await expect(page.getByRole("dialog")).toBeVisible();
  await expect(page.getByLabel("Konu", { exact: true })).toBeFocused();
  await page.keyboard.press("Escape");
  await expect(page.getByRole("dialog")).toHaveCount(0);
});
