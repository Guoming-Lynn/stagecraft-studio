import { chromium } from "@playwright/test";
import fs from "fs";
import path from "path";

const PORT = 8795;
const SCREENSHOT_DIR = "D:/geo_data/formal_atlas/screenshots";
const TEXT_DIR = "D:/geo_data/formal_atlas/screenshots";

async function run() {
  console.log("Launching Chromium for Step 3: Workspace and Gallery...");
  const browser = await chromium.launch({ headless: true });
  const context = await browser.newContext({ viewport: { width: 1440, height: 900 } });
  const page = await context.newPage();

  console.log(`Navigating to http://127.0.0.1:${PORT}/`);
  await page.goto(`http://127.0.0.1:${PORT}/`, { waitUntil: "networkidle" });

  console.log("Switching to Formal Analysis mode...");
  await page.getByRole("button", { name: "正式分析" }).click();

  // --- Workspace Tabs ---
  console.log("Switching to Workspace tab...");
  await page.getByRole("button", { name: "工作区" }).click();
  await page.waitForTimeout(500);

  // 1. Inputs Tab
  console.log("Viewing Workspace -> Inputs tab...");
  await page.getByRole("button", { name: "输入" }).click();
  await page.waitForTimeout(500);
  await page.screenshot({
    path: path.join(SCREENSHOT_DIR, "04_workspace_inputs.png"),
    fullPage: true
  });
  fs.writeFileSync(
    path.join(TEXT_DIR, "04_workspace_inputs_text.txt"),
    await page.innerText("body"),
    "utf-8"
  );
  console.log("Captured 04_workspace_inputs");

  // 2. Parameters Tab
  console.log("Viewing Workspace -> Parameters tab...");
  await page.getByRole("button", { name: "参数" }).click();
  await page.waitForTimeout(500);
  await page.screenshot({
    path: path.join(SCREENSHOT_DIR, "05_workspace_parameters.png"),
    fullPage: true
  });
  fs.writeFileSync(
    path.join(TEXT_DIR, "05_workspace_parameters_text.txt"),
    await page.innerText("body"),
    "utf-8"
  );
  console.log("Captured 05_workspace_parameters");

  // 3. Results Tab
  console.log("Viewing Workspace -> Results tab...");
  await page.getByRole("button", { name: "结果" }).click();
  await page.waitForTimeout(500);
  await page.screenshot({
    path: path.join(SCREENSHOT_DIR, "06_workspace_results.png"),
    fullPage: true
  });
  fs.writeFileSync(
    path.join(TEXT_DIR, "06_workspace_results_text.txt"),
    await page.innerText("body"),
    "utf-8"
  );
  console.log("Captured 06_workspace_results");

  // 4. Checks Tab
  console.log("Viewing Workspace -> Checks tab...");
  await page.getByRole("button", { name: "检查" }).click();
  await page.waitForTimeout(500);
  await page.screenshot({
    path: path.join(SCREENSHOT_DIR, "07_workspace_checks.png"),
    fullPage: true
  });
  fs.writeFileSync(
    path.join(TEXT_DIR, "07_workspace_checks_text.txt"),
    await page.innerText("body"),
    "utf-8"
  );
  console.log("Captured 07_workspace_checks");

  // 5. Logs Tab
  console.log("Viewing Workspace -> Logs tab...");
  await page.getByRole("button", { name: "日志" }).click();
  await page.waitForTimeout(500);
  await page.screenshot({
    path: path.join(SCREENSHOT_DIR, "08_workspace_logs.png"),
    fullPage: true
  });
  fs.writeFileSync(
    path.join(TEXT_DIR, "08_workspace_logs_text.txt"),
    await page.innerText("body"),
    "utf-8"
  );
  console.log("Captured 08_workspace_logs");

  // --- Gallery ---
  console.log("Switching to Gallery tab...");
  await page.getByRole("button", { name: "图库" }).click();
  await page.waitForTimeout(1000);
  await page.screenshot({
    path: path.join(SCREENSHOT_DIR, "09_gallery_overview.png"),
    fullPage: true
  });
  fs.writeFileSync(
    path.join(TEXT_DIR, "09_gallery_overview_text.txt"),
    await page.innerText("body"),
    "utf-8"
  );
  console.log("Captured 09_gallery_overview");

  // Click first figure card to open lightbox modal
  console.log("Opening first figure in lightbox modal...");
  const thumb = page.locator("div.thumb-img-wrap").first();
  if (await thumb.isVisible()) {
    await thumb.click();
    await page.waitForTimeout(500);
    const dialog = page.locator("dialog.lightbox");
    await dialog.waitFor({ state: "visible", timeout: 5000 });
    await page.screenshot({
      path: path.join(SCREENSHOT_DIR, "10_gallery_figure_modal.png"),
      fullPage: true
    });
    fs.writeFileSync(
      path.join(TEXT_DIR, "10_gallery_figure_modal_text.txt"),
      await page.innerText("body"),
      "utf-8"
    );
    console.log("Captured 10_gallery_figure_modal");
    await page.getByRole("button", { name: "关闭" }).click();
  } else {
    console.log("No thumb-img-wrap visible; skipping modal screenshot.");
  }

  await browser.close();
}

run().catch((err) => {
  console.error("Step 3 failed:", err);
  process.exit(1);
});
