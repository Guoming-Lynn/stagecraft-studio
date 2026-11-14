import os from "node:os";
import path from "node:path";

import { expect, test } from "@playwright/test";

test("drives formal design freeze, task console, human review gates, workspace checks, and gallery via GUI", async ({
  page,
}) => {
  const projectDir = path.join(
    os.tmpdir(),
    "stagecraft-studio-e2e",
    "formal_project",
  );
  const formalInput = path.join(projectDir, "synthetic_counts.h5ad");

  await page.goto("/");
  await page.getByRole("button", { name: "正式分析" }).click();
  await page.getByRole("button", { name: "研究设计" }).click();

  await page.getByLabel(/^目标基因/).fill("STAT1");
  await page.getByLabel("Harmony 整合变量").fill("dataset, donor_id");
  await page.getByLabel("数据路径").fill(formalInput);
  await page.getByPlaceholder("library").fill("L1");
  await page.getByPlaceholder("dataset").fill("D1");
  await page.getByPlaceholder("donor_id").fill("P1");
  await page.getByPlaceholder("source_block").fill("S1");
  await page.getByRole("button", { name: "冻结研究方案" }).click();
  await expect(page.getByText(/HARMONY_KEYS_ALLOWED/)).toBeVisible();

  await page.getByLabel("Harmony 整合变量").fill("dataset");
  await page.getByRole("button", { name: "冻结研究方案" }).click();
  await expect(page.locator("form p.hint")).toHaveText(/^[0-9a-f]{64}$/);

  await page.getByRole("button", { name: "前往工作区启动任务" }).click();

  const libRow = page.locator("table.task-library-table tbody tr").first();
  await libRow.getByRole("button", { name: "加载", exact: true }).click();
  await expect(libRow.locator("td").nth(3)).toContainText("COMPLETED", {
    timeout: 15_000,
  });

  await libRow.getByRole("button", { name: "质控", exact: true }).click();
  await expect(libRow.locator("td").nth(4)).toContainText("COMPLETED", {
    timeout: 15_000,
  });

  const pipelineBar = page.locator(".task-pipeline-bar");
  await pipelineBar.getByRole("button", { name: "合并主图谱" }).click();
  await expect(pipelineBar.locator(".task-cell-actions").nth(0)).toContainText(
    "COMPLETED",
    { timeout: 15_000 },
  );

  await pipelineBar.getByRole("button", { name: "计算分辨率网格" }).click();
  const openReviewBtn = pipelineBar.getByRole("button", {
    name: "前往审阅停点",
  });
  await expect(openReviewBtn).toBeVisible({ timeout: 20_000 });
  await openReviewBtn.click();

  await expect(page.getByText("科学审阅尚未完成")).toBeVisible();
  await page
    .locator(".review-wall")
    .getByRole("button", { name: /^0\.4/ })
    .click();
  await page
    .getByLabel("依据")
    .fill("ARTIFICIAL_E2E_FIXTURE: synthetic resolution choice");
  const confirmResBtn = page.getByRole("button", {
    name: "确认分辨率并生成审阅表",
  });
  await expect(confirmResBtn).toBeDisabled();
  await page.getByLabel("审阅人").fill("ARTIFICIAL_E2E_REVIEWER");
  await expect(confirmResBtn).toBeEnabled();
  await confirmResBtn.click();

  await expect(
    page.getByRole("heading", { name: "细胞群（cluster）" }),
  ).toBeVisible({ timeout: 15_000 });

  await page.getByRole("button", { name: "表格" }).click();
  await expect(
    page.getByRole("cell", { name: "UMI / 细胞" }).first(),
  ).toBeVisible();
  await page.getByRole("tab", { name: "Marker 证据" }).click();
  await expect(page.getByRole("cell", { name: "LYZ" })).toBeVisible();
  await expect(page.getByRole("cell", { name: "CD3D" })).toBeVisible();

  await page
    .getByLabel("依据")
    .fill("ARTIFICIAL_E2E_FIXTURE: synthetic keep all clusters");
  await page.getByRole("button", { name: "提交群体去留决定" }).click();

  await expect(
    page.getByRole("button", { name: "提交命名并锁定 Part 1" }),
  ).toBeVisible();
  const nameInputs = page.locator("table.review-table tbody input");
  await expect(nameInputs).toHaveCount(2);
  await nameInputs.nth(0).fill("Monocyte");
  await nameInputs.nth(1).fill("T_cell");
  const lockTrigger = page.waitForResponse(
    (resp) =>
      resp.url().includes("/clusters") && resp.request().method() === "POST",
  );
  await page.getByRole("button", { name: "提交命名并锁定 Part 1" }).click();
  await lockTrigger;

  await page.getByRole("button", { name: "工作区" }).click();
  await page.getByRole("button", { name: "任务", exact: true }).click();
  await expect(page.getByText("LOCKED", { exact: true })).toBeVisible({
    timeout: 20_000,
  });

  const part2Block = page
    .locator(".task-stage-block")
    .filter({ hasText: "Part 2 全局描述与图表" });
  await part2Block.getByRole("button", { name: "运行 Part 2 汇总" }).click();
  await expect(part2Block.locator(".task-status")).toHaveText("COMPLETED", {
    timeout: 15_000,
  });
  await part2Block.getByRole("button", { name: "生成 Part 2 图表" }).click();
  await expect(part2Block.locator(".task-status")).toHaveText("COMPLETED", {
    timeout: 15_000,
  });

  const part3Block = page
    .locator(".task-stage-block")
    .filter({ hasText: "Part 3 亚群重聚类" });
  await part3Block.getByLabel("目标谱系 / 细胞群").fill("Monocyte");
  await part3Block.getByRole("button", { name: "运行亚群重聚类" }).click();
  await expect(part3Block.locator(".task-status")).toHaveText("COMPLETED", {
    timeout: 15_000,
  });

  await page.getByRole("button", { name: "审阅", exact: true }).click();
  await page.getByRole("tab", { name: "亚群重聚类审阅（Part 3）" }).click();
  await expect(page.getByLabel("审阅人")).toHaveValue(
    "ARTIFICIAL_E2E_REVIEWER",
  );
  await page
    .getByLabel("亚群重聚类审阅（Part 3）")
    .getByLabel("依据")
    .fill("ARTIFICIAL_E2E_FIXTURE: Part 3 resolution");
  await page.getByRole("button", { name: "提交停点 1 分辨率审阅" }).click();
  await expect(page.getByText("停点 1 已完成")).toBeVisible({
    timeout: 15_000,
  });

  await page.getByRole("button", { name: "工作区" }).click();
  await page.getByRole("button", { name: "任务", exact: true }).click();

  const part5Block = page
    .locator(".task-stage-block")
    .filter({ hasText: "Part 5 供体级模型准备与拟合" });
  await part5Block.getByLabel("分析细胞群（Arm）").fill("Monocyte");
  await part5Block.getByLabel("分组列").fill("condition");
  await part5Block
    .getByRole("button", { name: "运行 Part 5 准备/拟合" })
    .click();
  await expect(part5Block.locator(".task-status")).toHaveText("COMPLETED", {
    timeout: 15_000,
  });

  const reportBar = page.locator(".task-report-bar");
  await reportBar.getByRole("button", { name: "生成阶段报告" }).click();
  await expect(reportBar.locator(".task-status")).toHaveText("COMPLETED", {
    timeout: 15_000,
  });

  await page.getByRole("button", { name: "检查" }).click();
  await expect(
    page.getByRole("cell", { name: "DONOR_MAPPING_REQUIRED" }).first(),
  ).toBeVisible();
  await expect(
    page.getByRole("cell", { name: "DESIGN_ESTIMABLE" }).first(),
  ).toBeVisible();

  await page.getByRole("button", { name: "结果" }).click();
  await expect(
    page.getByRole("cell", { name: /REPORT\.md/ }).first(),
  ).toBeVisible();

  await page.getByRole("button", { name: "图库" }).click();
  await expect(
    page.getByText(/NOT_ESTABLISHED_FOR_THIS_ANALYSIS/),
  ).toBeVisible();
  await expect(page.getByText(/NOT_ESTIMABLE/).first()).toBeVisible();
});
