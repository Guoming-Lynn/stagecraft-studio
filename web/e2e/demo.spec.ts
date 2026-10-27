import { expect, test } from "@playwright/test";

test("opens the demo, a figure, and the reproduction bundle", async ({
  page,
}) => {
  await page.goto("/");
  await page.getByRole("button", { name: "助手" }).click();
  await expect(page.getByText(/本地解释模式/)).toBeVisible();
  await page.getByRole("button", { name: "检查发送内容" }).click();
  await expect(page.getByText("仅本地")).toBeVisible();
  await page.getByRole("button", { name: "查看本地解释" }).click();
  await expect(
    page.getByText("请选择正式阶段读取摘要，也可以直接查看字段和规则说明。"),
  ).toBeVisible();
  await page.getByRole("button", { name: "运行演示" }).click();
  await expect(page.getByRole("heading", { name: /速览已跑到/ })).toBeVisible();
  await expect(page.getByText("已完成", { exact: true }).first()).toBeVisible();
  await page.getByLabel("界面语言").selectOption("en-US");
  await expect(page.getByRole("button", { name: "Figures" })).toBeVisible();
  await page.getByLabel("Interface language").selectOption("zh-CN");
  await page.getByRole("button", { name: "图像" }).click();
  await page.getByRole("button", { name: /volcano\.png/ }).click();
  await expect(page.locator("dialog")).toBeVisible();
  const downloadPromise = page.waitForEvent("download");
  await page.getByRole("link", { name: "下载复现包" }).click();
  const download = await downloadPromise;
  expect(download.suggestedFilename()).toMatch(/\.zip$/);
});

test("keeps model proposals behind explicit authorization", async ({
  page,
}) => {
  const provider = {
    config: {
      provider: "openai",
      base_url: "http://127.0.0.1:9999/v1",
      model: "mock-model",
      timeout_seconds: 30,
      max_output_tokens: 1024,
      context_chars: 16000,
      call_limit: 20,
    },
    capabilities: {
      text: true,
      streaming: false,
      structured_output: true,
      tool_calling: true,
      probed: true,
    },
    key_storage: "session",
    calls_used: 0,
  };
  await page.route("**/api/assistant/provider", async (route) => {
    if (route.request().method() === "GET") {
      await route.fulfill({ json: provider });
      return;
    }
    await route.fulfill({ json: provider });
  });
  await page.route("**/api/assistant/preview", async (route) => {
    await route.fulfill({
      json: {
        preview_id: "e".repeat(32),
        input_hash: "f".repeat(64),
        payload: {
          topic: "annotation",
          marker_evidence: [{ cluster_id: "0", marker_genes: ["LYZ"] }],
        },
        sources: [{ ref: "stage/1", hash: "a".repeat(64) }],
        mode: "tools",
        local_text:
          "可读取 1 个阶段证据中的 cluster marker 摘要；候选名称只作人工参考。",
      },
    });
  });
  await page.route("**/api/assistant/call", async (route) => {
    await route.fulfill({
      json: {
        call_id: "1".repeat(32),
        status: "COMPLETED",
        text: "已生成只读候选。",
        model: "mock-model",
        prompt_version: "m6-summary-v1",
        input_hash: "f".repeat(64),
        sources: [{ ref: "stage/1", hash: "a".repeat(64) }],
        created_at: new Date().toISOString(),
        usage: null,
        proposal: {
          id: 1,
          kind: "cluster_annotation",
          values: {
            cluster_id: "0",
            candidate_name: "Myeloid_like",
            marker_genes: ["LYZ"],
            rationale: "候选依据只来自授权 marker 摘要。",
          },
          rationale: "仅供人工参考。",
          status: "DRAFT",
          note: "不会写入 cluster 命名或审阅记录。",
        },
        auxiliary: true,
      },
    });
  });
  await page.goto("/");
  await page.getByRole("button", { name: "助手" }).click();
  await page.getByRole("button", { name: "模型连接设置" }).click();
  await expect(page.getByText("结构化工具已连接")).toBeVisible();
  await page.getByLabel("内容").selectOption("annotation");
  await page.getByRole("button", { name: "检查发送内容" }).click();
  await page
    .getByText("我已检查摘要内容，并同意将其发送至当前模型服务。")
    .click();
  await page.getByRole("button", { name: "发送给模型" }).click();
  await expect(page.getByText("Myeloid_like")).toBeVisible();
  await expect(
    page.getByText("Proposal · DRAFT · 只读候选", { exact: true }),
  ).toBeVisible();
  await expect(
    page.getByRole("button", { name: "转入研究设计表单" }),
  ).toHaveCount(0);
});

test("can cancel an in-flight model call without changing the workspace", async ({
  page,
}) => {
  const provider = {
    config: {
      provider: "openai",
      base_url: "http://127.0.0.1:9999/v1",
      model: "slow-model",
      timeout_seconds: 30,
      max_output_tokens: 1024,
      context_chars: 16000,
      call_limit: 20,
    },
    capabilities: {
      text: true,
      streaming: false,
      structured_output: false,
      tool_calling: true,
      probed: true,
    },
    key_storage: "session",
    calls_used: 0,
  };
  let cancelCalls = 0;
  let releaseCall: (() => void) | null = null;
  await page.route("**/api/assistant/provider", async (route) => {
    await route.fulfill({ json: provider });
  });
  await page.route("**/api/assistant/preview", async (route) => {
    await route.fulfill({
      json: {
        preview_id: "a".repeat(32),
        input_hash: "b".repeat(64),
        payload: { topic: "stage" },
        sources: [],
        mode: "tools",
        local_text: "摘要已准备。",
      },
    });
  });
  await page.route("**/api/assistant/call", async (route) => {
    const currentRoute = route;
    await new Promise<void>((resolve) => {
      releaseCall = resolve;
    });
    await currentRoute.fulfill({
      json: {
        call_id: "3".repeat(32),
        status: "CANCELLED",
        text: "助手调用已取消。",
        model: "slow-model",
        prompt_version: "m6-summary-v1",
        input_hash: "b".repeat(64),
        sources: [],
        created_at: new Date().toISOString(),
        usage: null,
        proposal: null,
        auxiliary: true,
      },
    });
  });
  await page.route("**/api/assistant/calls/*/cancel", async (route) => {
    cancelCalls += 1;
    releaseCall?.();
    await route.fulfill({ json: { cancelled: true } });
  });
  await page.goto("/");
  await page.getByRole("button", { name: "助手" }).click();
  await page.getByRole("button", { name: "检查发送内容" }).click();
  await page
    .getByText("我已检查摘要内容，并同意将其发送至当前模型服务。")
    .click();
  await page.getByRole("button", { name: "发送给模型" }).click();
  await page.getByTestId("right").getByRole("button", { name: "取消" }).click();
  expect(cancelCalls).toBe(1);
  await expect(page.getByText("辅助内容")).toHaveCount(0);
  await expect(
    page.getByRole("button", { name: "检查发送内容" }),
  ).toBeEnabled();
});

test("moves a protocol proposal into the design form without freezing it", async ({
  page,
}) => {
  const provider = {
    config: {
      provider: "openai",
      base_url: "http://127.0.0.1:9999/v1",
      model: "mock-model",
      timeout_seconds: 30,
      max_output_tokens: 1024,
      context_chars: 16000,
      call_limit: 20,
    },
    capabilities: {
      text: true,
      streaming: false,
      structured_output: true,
      tool_calling: true,
      probed: true,
    },
    key_storage: "session",
    calls_used: 0,
  };
  let freezeCalls = 0;
  await page.route("**/api/assistant/provider", async (route) => {
    await route.fulfill({ json: provider });
  });
  await page.route("**/api/assistant/preview", async (route) => {
    await route.fulfill({
      json: {
        preview_id: "c".repeat(32),
        input_hash: "d".repeat(64),
        payload: { topic: "proposal" },
        sources: [],
        mode: "tools",
        local_text: "配置草案可以由用户检查后进入研究设计表单。",
      },
    });
  });
  await page.route("**/api/assistant/call", async (route) => {
    await route.fulfill({
      json: {
        call_id: "2".repeat(32),
        status: "COMPLETED",
        text: "配置草案已生成。请检查后转入研究设计表单。",
        model: "mock-model",
        prompt_version: "m6-summary-v1",
        input_hash: "d".repeat(64),
        sources: [],
        created_at: new Date().toISOString(),
        usage: null,
        proposal: {
          id: 2,
          kind: "protocol_config",
          values: {
            target_gene: "STAT1",
            species: "human",
            harmony_keys: ["dataset"],
            loose_min_genes: 250,
          },
          rationale: "保持 dataset 作为批次校正键。",
          status: "DRAFT",
          note: "仅为草案。",
        },
        auxiliary: true,
      },
    });
  });
  await page.route("**/api/protocol/freeze", async (route) => {
    freezeCalls += 1;
    await route.fulfill({
      status: 500,
      json: { detail: "must not be called" },
    });
  });
  await page.goto("/");
  await page.getByRole("button", { name: "助手" }).click();
  await page.getByLabel("内容").selectOption("proposal");
  await page.getByRole("button", { name: "检查发送内容" }).click();
  await page
    .getByText("我已检查摘要内容，并同意将其发送至当前模型服务。")
    .click();
  await page.getByRole("button", { name: "发送给模型" }).click();
  await page.getByRole("button", { name: "转入研究方案表单" }).click();
  await expect(page.getByRole("heading", { name: "研究设计" })).toBeVisible();
  await expect(page.getByRole("textbox", { name: /^目标基因/ })).toHaveValue(
    "STAT1",
  );
  await expect(
    page.getByRole("textbox", { name: /^最低检出基因数/ }),
  ).toHaveValue("250");
  expect(freezeCalls).toBe(0);
});
