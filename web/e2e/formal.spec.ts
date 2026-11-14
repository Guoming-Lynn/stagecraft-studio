import os from "node:os";
import path from "node:path";

import { expect, type APIRequestContext, test } from "@playwright/test";

const ORIGIN = "http://127.0.0.1:8771";

type StageJob = {
  id: number;
  task_id: string;
  job_status: string;
};

async function enqueueAndWait(
  request: APIRequestContext,
  token: string,
  runId: number,
  taskId: string,
  fields: Record<string, unknown>,
): Promise<void> {
  const response = await request.post(`/api/stage-runs/${runId}/jobs`, {
    headers: { origin: ORIGIN, "x-stagecraft-token": token },
    data: { task_id: taskId, fields },
  });
  expect(response.status()).toBe(201);
  const queued = (await response.json()) as { id: number };
  await expect
    .poll(
      async () => {
        const listResp = await request.get(`/api/stage-runs/${runId}/jobs`);
        const jobs = (await listResp.json()) as StageJob[];
        return jobs.find((item) => item.id === queued.id)?.job_status ?? "";
      },
      { timeout: 15_000 },
    )
    .toBe("COMPLETED");
}

test("drives formal design freeze, Part 1 human review gates, workspace checks, and gallery", async ({
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

  const boot = (await (await page.request.get("/api/bootstrap")).json()) as {
    token: string;
  };
  const runs = (await (await page.request.get("/api/stage-runs")).json()) as {
    id: number;
  }[];
  expect(runs.length).toBeGreaterThan(0);
  const runId = runs[runs.length - 1].id;

  await enqueueAndWait(page.request, boot.token, runId, "formal_part1_load", {
    library_id: "L1",
    input: formalInput,
    format: "h5ad",
  });
  await enqueueAndWait(page.request, boot.token, runId, "formal_part1_qc", {
    library_id: "L1",
    source: formalInput,
    config: path.join(projectDir, "qc_config.json"),
  });
  await enqueueAndWait(page.request, boot.token, runId, "formal_part1_merge", {
    gene: "STAT1",
  });
  await enqueueAndWait(page.request, boot.token, runId, "formal_part1_grid", {
    common: path.join(
      projectDir,
      "analysis",
      `stage_${runId}`,
      "formal_part1_merge",
      "primary_common.h5ad",
    ),
    gene: "STAT1",
    config: path.join(projectDir, "grid_config.json"),
  });

  await page.getByRole("button", { name: "审阅", exact: true }).click();
  await expect(page.getByText("科学审阅尚未完成")).toBeVisible();
  await page
    .locator(".review-wall")
    .getByRole("button", { name: /^0\.4/ })
    .click();
  await page
    .getByLabel("依据")
    .fill("ARTIFICIAL_E2E_FIXTURE: synthetic resolution choice");
  await page.getByRole("button", { name: "确认分辨率并生成审阅表" }).click();

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
  await page.getByRole("button", { name: "提交命名并锁定 Part 1" }).click();

  await expect
    .poll(
      async () => {
        const listResp = await page.request.get(
          `/api/stage-runs/${runId}/jobs`,
        );
        const jobs = (await listResp.json()) as StageJob[];
        return (
          jobs.find((item) => item.task_id === "formal_part1_lock")
            ?.job_status ?? ""
        );
      },
      { timeout: 15_000 },
    )
    .toBe("COMPLETED");

  await enqueueAndWait(
    page.request,
    boot.token,
    runId,
    "formal_part5_prepare",
    {
      input: path.join(
        projectDir,
        "analysis",
        `stage_${runId}`,
        "formal_part1_lock",
        "locked_atlas.h5ad",
      ),
      gene: "STAT1",
      group: "condition",
      arm: "Monocyte",
    },
  );

  await page.getByRole("button", { name: "工作区" }).click();
  await page.getByRole("button", { name: "检查" }).click();
  await expect(
    page.getByRole("cell", { name: "DONOR_MAPPING_REQUIRED" }).first(),
  ).toBeVisible();
  await expect(
    page.getByRole("cell", { name: "DESIGN_ESTIMABLE" }).first(),
  ).toBeVisible();

  await page.getByRole("button", { name: "图库" }).click();
  await expect(
    page.getByText(/NOT_ESTABLISHED_FOR_THIS_ANALYSIS/),
  ).toBeVisible();
  await expect(page.getByText(/NOT_ESTIMABLE/).first()).toBeVisible();
});
