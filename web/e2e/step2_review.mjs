import { chromium } from "@playwright/test";
import fs from "fs";
import path from "path";

const PORT = 8795;
const SCREENSHOT_DIR = "D:/geo_data/formal_atlas/screenshots";
const TEXT_DIR = "D:/geo_data/formal_atlas/screenshots";

// Biological lineage hierarchy for PBMC clusters
const DEFAULT_NAMES = [
  "CD4_T_cells",
  "CD14_Monocytes",
  "B_cells",
  "CD8_T_cells",
  "NK_cells",
  "FCGR3A_Monocytes",
  "Dendritic_cells",
  "Platelets",
  "Plasmacytoid_DCs",
  "Proliferating_T_cells",
  "Plasma_cells",
  "Hematopoietic_stem_cells"
];

async function run() {
  console.log("Launching Chromium for Step 2: Review Center...");
  const browser = await chromium.launch({ headless: true });
  const context = await browser.newContext({ viewport: { width: 1440, height: 900 } });
  const page = await context.newPage();

  console.log(`Navigating to http://127.0.0.1:${PORT}/`);
  await page.goto(`http://127.0.0.1:${PORT}/`, { waitUntil: "networkidle" });

  console.log("Switching to Formal Analysis mode...");
  await page.getByRole("button", { name: "正式分析" }).click();

  console.log("Switching to Review tab...");
  await page.getByRole("button", { name: "审阅" }).click();

  console.log("Waiting for Review Center resolution tiles...");
  const wall = page.locator("div.review-wall");
  await wall.waitFor({ state: "visible", timeout: 15000 });

  // Click resolution 0.2
  console.log("Selecting resolution 0.2...");
  const resBtn = wall.locator("button").filter({ hasText: /^0\.2/ }).first();
  await resBtn.click();
  await page.waitForTimeout(500);

  // Find table rows
  const rows = page.locator("table tbody tr");
  await rows.first().waitFor({ state: "visible", timeout: 10000 });
  const count = await rows.count();
  console.log(`Detected ${count} clusters in table at resolution 0.2`);

  // Fill biological names
  for (let i = 0; i < count; i++) {
    const clusterId = (await rows.nth(i).locator("td").first().innerText()).trim();
    const cellName = DEFAULT_NAMES[i] || `Lineage_cluster_${clusterId}`;
    console.log(`Naming Cluster ${clusterId} -> ${cellName}`);
    const nameInput = rows.nth(i).locator("td").nth(2).locator("input");
    await nameInput.fill(cellName);
  }

  // Rationale
  const rationaleInput = page.locator("label:has-text('分辨率') input");
  await rationaleInput.fill("PBMC major lineage markers on consensus grid");

  await page.waitForTimeout(500);
  const shotPath1 = path.join(SCREENSHOT_DIR, "02_review_center_annotating.png");
  await page.screenshot({ path: shotPath1, fullPage: true });
  console.log("Saved screenshot:", shotPath1);

  const textPath1 = path.join(TEXT_DIR, "02_review_center_annotating_text.txt");
  fs.writeFileSync(textPath1, await page.innerText("body"), "utf-8");
  console.log("Saved page text:", textPath1);

  // Click submit review
  console.log("Clicking '提交审阅'...");
  await page.getByRole("button", { name: "提交审阅" }).click();

  // Wait for submission confirmation
  const confirmHint = page.locator("form p.hint:has-text('提交审阅')");
  await confirmHint.waitFor({ state: "visible", timeout: 10000 });
  await page.waitForTimeout(500);
  const shotPath2 = path.join(SCREENSHOT_DIR, "03_review_center_submitted.png");
  await page.screenshot({ path: shotPath2, fullPage: true });
  console.log("Saved screenshot:", shotPath2);

  const textPath2 = path.join(TEXT_DIR, "03_review_center_submitted_text.txt");
  fs.writeFileSync(textPath2, await page.innerText("body"), "utf-8");
  console.log("Saved page text:", textPath2);

  await browser.close();
}

run().catch((err) => {
  console.error("Step 2 failed:", err);
  process.exit(1);
});
