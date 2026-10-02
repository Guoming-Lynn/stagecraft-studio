import { chromium } from "@playwright/test";
import fs from "fs";
import path from "path";

const PORT = 8795;
const SCREENSHOT_DIR = "D:/geo_data/formal_atlas/screenshots";
const TEXT_DIR = "D:/geo_data/formal_atlas/screenshots";

const LIBRARIES = [
  { id: "GSM8596781_G", ds: "GSE280401" },
  { id: "GSM8596782_O", ds: "GSE280401" },
  { id: "GSM8596783_B", ds: "GSE280401" },
  { id: "GSM8596784_D", ds: "GSE280401" },
  { id: "GSM7421504_HC1", ds: "GSE233275" },
  { id: "GSM7421505_HC2", ds: "GSE233275" },
  { id: "GSM7421506_HC3", ds: "GSE233275" },
  { id: "GSM7421507_HC4", ds: "GSE233275" },
  { id: "GSM7421508_INS1", ds: "GSE233275" },
  { id: "GSM7421509_INS2", ds: "GSE233275" },
  { id: "GSM7421510_INS3", ds: "GSE233275" },
  { id: "GSM7421511_INS4", ds: "GSE233275" },
  { id: "GSM8397940_NT1", ds: "GSE272294" },
  { id: "GSM8397941_LL1", ds: "GSE272294" },
  { id: "GSM8397942_NT2", ds: "GSE272294" },
  { id: "GSM8397943_LL2", ds: "GSE272294" }
];

async function run() {
  console.log("Launching Chromium for Step 1: Research Design...");
  const browser = await chromium.launch({ headless: true });
  const context = await browser.newContext({ viewport: { width: 1440, height: 900 } });
  const page = await context.newPage();

  console.log(`Navigating to http://127.0.0.1:${PORT}/`);
  await page.goto(`http://127.0.0.1:${PORT}/`, { waitUntil: "networkidle" });

  console.log("Switching to Formal Analysis mode...");
  await page.getByRole("button", { name: "正式分析" }).click();

  console.log("Switching to Research Design tab...");
  await page.getByRole("button", { name: "研究设计" }).click();

  await page.waitForSelector("h2:has-text('研究设计')");

  console.log("Filling in Protocol form fields...");
  await page.getByRole("textbox", { name: /^目标基因/ }).fill("STAT1");
  await page.locator("label").filter({ hasText: /^物种/ }).locator("select").selectOption("human");
  await page.getByRole("textbox", { name: /^Harmony 键/ }).fill("dataset");
  await page.getByRole("textbox", { name: /^宽松基因数/ }).fill("200");
  await page.getByRole("textbox", { name: /^数据路径/ }).fill("D:/geo_data/formal_atlas/data.h5ad");

  console.log("Adding 15 library rows (total 16)...");
  const addBtn = page.getByRole("button", { name: "+ library" });
  for (let i = 0; i < 15; i++) {
    await addBtn.click();
  }

  const libInputs = page.locator("input[placeholder='library']");
  const dsInputs = page.locator("input[placeholder='dataset']");

  for (let i = 0; i < LIBRARIES.length; i++) {
    await libInputs.nth(i).fill(LIBRARIES[i].id);
    await dsInputs.nth(i).fill(LIBRARIES[i].ds);
  }

  console.log("Clicking '冻结协议'...");
  await page.getByRole("button", { name: "冻结协议" }).click();

  console.log("Waiting for protocol hash...");
  const hintLocator = page.locator("form p.hint");
  await hintLocator.waitFor({ state: "visible", timeout: 15000 });
  const hashText = await hintLocator.innerText();
  console.log("Protocol frozen successfully, hash:", hashText);

  await page.waitForTimeout(1000);
  const shotPath = path.join(SCREENSHOT_DIR, "01_research_design_frozen.png");
  await page.screenshot({ path: shotPath, fullPage: true });
  console.log("Saved screenshot:", shotPath);

  const bodyText = await page.innerText("body");
  const textPath = path.join(TEXT_DIR, "01_research_design_text.txt");
  fs.writeFileSync(textPath, bodyText, "utf-8");
  console.log("Saved page text:", textPath);

  await browser.close();
}

run().catch((err) => {
  console.error("Step 1 failed:", err);
  process.exit(1);
});
