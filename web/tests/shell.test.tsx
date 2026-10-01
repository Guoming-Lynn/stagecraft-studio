import { act, type ReactNode } from "react";
import { createRoot, type Root } from "react-dom/client";
import { afterEach, describe, expect, it } from "vitest";

import type { Bootstrap, RunView, StepView } from "../src/api/client";
import { saveLayout } from "../src/layout_store";
import { lineClass } from "../src/log_lines";
import { shouldNotify } from "../src/notify";
import { Assistant } from "../src/panes/Assistant";
import { Images } from "../src/panes/Images";
import { StartForm } from "../src/panes/StartForm";
import { StepDetail } from "../src/panes/StepDetail";
import { Steps } from "../src/panes/Steps";

const hosts: { root: Root; host: HTMLElement }[] = [];

afterEach(() => {
  for (const item of hosts) {
    act(() => item.root.unmount());
    item.host.remove();
  }
  hosts.length = 0;
  localStorage.clear();
});

describe("shell", () => {
  it("keeps only numeric layout sizes", () => {
    const mixed: Record<string, number> = { left: 22 };
    Object.assign(mixed, { note: "D:\\data" });
    saveLayout(mixed);
    const saved = localStorage.getItem("stagecraft.layout") ?? "";
    expect(saved).toContain("22");
    expect(saved).not.toContain("D:");
  });

  it("marks error and warning log lines", () => {
    expect(lineClass("ERROR failed")).toBe("log-error");
    expect(lineClass("WARNING slow")).toBe("log-warning");
  });

  it("shows the status text it was given", () => {
    const host = mount(
      <Steps
        steps={[step("running", "运行中")]}
        selected="quicklook_qc"
        onSelect={() => undefined}
      />,
    );
    expect(host.textContent).toContain("运行中");
    expect(host.textContent).toContain("质控与双细胞");
  });

  it("shows figure reasons from the payload", () => {
    const host = mount(
      <Images run={run()} focus="" onFocus={() => undefined} />,
    );
    expect(host.textContent).toContain("不通过");
    expect(host.textContent).toContain("该面板没有细胞数超过 100 的类别");
    expect(host.textContent).not.toContain("empty_violin");
  });

  it("leaves the assistant disconnected", () => {
    expect(mount(<Assistant />).textContent).toContain("未接入");
  });

  it("shows the server group note and not an engine path field", () => {
    const host = mount(
      <StartForm
        bootstrap={bootstrap()}
        onStarted={() => undefined}
        onDemo={() => undefined}
      />,
    );
    expect(host.textContent).toContain("没有分组时不出 case/control 对比图");
    expect(host.textContent).toContain(
      "留空时联网下载人和鼠的 Hallmark、KEGG、GOBP",
    );
    expect(host.textContent).toContain("鼠");
    expect(host.textContent).toContain("运行演示");
    expect(host.textContent).toContain("不是策展数据");
    expect(host.querySelector("[name=python_path]")).toBeNull();
    expect(host.textContent).toContain("python.exe");
  });

  it("renders engine input and figure status from the run", () => {
    const host = mount(
      <StepDetail run={run()} step={step("done", "完成")} source={null} />,
    );
    expect(host.textContent).toContain("速览已跑到聚类");
    expect(host.textContent).toContain("已完成");
    expect(host.textContent).toContain("分析已完成");
    expect(host.textContent).toContain("未通过");
    expect(host.querySelector(".log-error")?.textContent).toContain("ERROR");
    const parameters = [...host.querySelectorAll("button")].find(
      (button) => button.textContent === "参数",
    );
    act(() =>
      parameters?.dispatchEvent(new MouseEvent("click", { bubbles: true })),
    );
    expect(host.textContent).toContain("用户填写");
    expect(host.textContent).toContain("细胞水平");
    expect(host.textContent).toContain("下载复现包");
  });

  it("notifies only after a granted run leaves the running state", () => {
    expect(shouldNotify("running", "succeeded", "granted")).toBe(true);
    expect(shouldNotify("starting", "failed", "granted")).toBe(true);
    expect(shouldNotify("", "succeeded", "granted")).toBe(false);
    expect(shouldNotify("running", "succeeded", "default")).toBe(false);
    expect(shouldNotify("succeeded", "succeeded", "granted")).toBe(false);
  });
});

function mount(node: ReactNode): HTMLElement {
  const host = document.createElement("div");
  document.body.append(host);
  const root = createRoot(host);
  act(() => root.render(node));
  hosts.push({ root, host });
  return host;
}

function step(status: string, label: string): StepView {
  return {
    step_id: "quicklook_qc",
    name: "质控与双细胞",
    status,
    status_label: label,
    script_name: "phase01_qc_scrublet.py",
    artifacts: [],
  };
}

function bootstrap(): Bootstrap {
  return {
    token: "secret",
    python: "D:\\engines\\python.exe",
    script: "D:\\engines\\run_pipeline.py",
    gmt: "",
    group_note: "没有分组时不出 case/control 对比图",
    engine_name: "scrna-target-engine",
    engine_version: "0.1.0",
    engine_git: "abc",
    environment_ok: true,
    demo_source:
      "合成矩阵，由 write_demo_h5ad.py 用种子 42 生成。不是策展数据，不能当作正式分析。",
  };
}

function run(): RunView {
  return {
    run_id: "abc123abc123abcd",
    task_id: "quicklook_run",
    status: "succeeded",
    status_label: "已完成",
    heading: "速览已跑到聚类",
    lede: "产物标记为 quicklook。它不能当作正式分析的输入。",
    can_cancel: false,
    returncode: 0,
    enrichment: "not_run_until_local_gmt",
    enrichment_label: "未运行，等本地基因集",
    stopped_after: "phase03",
    output_root: "D:\\out",
    engine_name: "scrna-target-engine",
    engine_version: "0.1.0",
    engine_git: "abc",
    command: ["python", "run_pipeline.py"],
    command_line: "python run_pipeline.py",
    config_text: "{}",
    parameters: [
      {
        name: "TARGET_GENE",
        value: "IFITM3",
        source: "user",
        source_label: "用户填写",
      },
    ],
    logs: [{ name: "phase.log", text: "ERROR boom" }],
    pipeline_outcome: "completed_analysis",
    pipeline_label: "分析已完成",
    figure_status: "reject",
    figure_label: "未通过",
    methods_text:
      "本段按固定模板写成，没有调用模型。分析在细胞水平进行，结果是探索性的，标签是临时的。",
    images: [
      {
        rel: "04_figures/volcano.png",
        step_id: "quicklook_qc",
        step_name: "质控与双细胞",
        passed: false,
        label: "不通过",
        reasons: [
          {
            code: "empty_violin",
            text: "该面板没有细胞数超过 100 的类别",
            suggestion: "检查这个分组里是否还有细胞，或换一个有细胞的类别。",
          },
        ],
      },
    ],
  };
}
