import { expect, test } from "@playwright/test";

test("opens the demo, a figure, and the reproduction bundle", async ({
  page,
}) => {
  await page.goto("/");
  await page.getByRole("button", { name: "运行演示" }).click();
  await expect(page.getByRole("heading", { name: /速览已跑到/ })).toBeVisible();
  await expect(page.getByText("已完成", { exact: true }).first()).toBeVisible();
  await page.getByRole("button", { name: /volcano\.png/ }).click();
  await expect(page.locator("dialog")).toBeVisible();
  const downloadPromise = page.waitForEvent("download");
  await page.getByRole("link", { name: "下载复现包" }).click();
  const download = await downloadPromise;
  expect(download.suggestedFilename()).toMatch(/\.zip$/);
});
