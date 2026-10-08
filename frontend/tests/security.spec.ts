import { test, expect } from "@playwright/test";

test("staff sees security page, audit log and assistant mode; customer toggles e-mail preference", async ({
  page,
  browser,
}) => {
  await page.goto("/");
  await page.getByRole("button", { name: /Destek yönetimi/ }).click();
  await page.getByRole("button", { name: "Güvenlik", exact: true }).click();
  await expect(
    page.getByRole("heading", { name: "Güvenlik ve denetim" }),
  ).toBeVisible();
  await expect(page.getByText("Yürürlükteki ayarlar")).toBeVisible();
  await expect(page.getByRole("link", { name: "CSV indir" })).toBeVisible();
  await expect(
    page.getByRole("cell", { name: "Giriş yapıldı" }).first(),
  ).toBeVisible();
  await page.getByRole("button", { name: "Firmalar", exact: true }).click();
  const mode = page.getByLabel("Atlas Teknoloji asistan modu");
  await expect(mode).toBeVisible();
  await mode.selectOption("off");
  await expect(page.getByText("Değişiklik kaydedildi.")).toBeVisible();
  await page.getByRole("button", { name: "Güvenlik", exact: true }).click();
  await expect(
    page.getByRole("cell", { name: "Firma erişimi güncellendi" }).first(),
  ).toBeVisible();

  const customerContext = await browser.newContext();
  const customer = await customerContext.newPage();
  await customer.goto("/");
  await customer.getByRole("button", { name: /Müşteri alanı/ }).click();
  await customer.getByRole("button", { name: /Bildirimler/ }).click();
  const toggle = customer.getByRole("checkbox", {
    name: /E-posta ile de bilgilendir/,
  });
  await expect(toggle).toBeVisible();
  await expect(toggle).toBeDisabled();
  await expect(
    customer.getByText("E-posta gönderimi bu kurulumda yapılandırılmamış."),
  ).toBeVisible();
  await customerContext.close();
});
