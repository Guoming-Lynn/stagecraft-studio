import { act, type ReactNode } from "react";
import { createRoot, type Root } from "react-dom/client";
import { afterEach, describe, expect, it } from "vitest";

import type { StageWorkspaceView } from "../src/api/client";
import { WorkspaceTasks } from "../src/panes/WorkspaceTasks";
import {
  extractLockedCellTypes,
  extractProtocolLibraries,
  hasActiveFormalJobs,
  latestTaskStatus,
} from "../src/panes/workspace_task_helpers";
import { readReviewer, saveReviewer, todayIso } from "../src/reviewer_store";

const hosts: { root: Root; host: HTMLElement }[] = [];

afterEach(() => {
  for (const item of hosts) {
    act(() => item.root.unmount());
    item.host.remove();
  }
  hosts.length = 0;
  localStorage.clear();
});

function sampleWorkspace(): StageWorkspaceView {
  return {
    id: 7,
    stage_status: "ACTIVE",
    invalidated: false,
    inputs: {
      project_id: 1,
      project_name: "STAT1",
      root_path: "D:\\proj",
      protocol_id: 1,
      protocol_hash: "a".repeat(64),
      input_hash: "b".repeat(64),
      target_gene: "STAT1",
      species: "human",
      data_path: "counts.h5ad",
      document: {
        target_gene: "STAT1",
        manifest: [
          {
            library_id: "L1",
            dataset: "D1",
            donor_id: "P1",
            source_block: "S1",
          },
          {
            library_id: "L2",
            dataset: "D2",
            donor_id: "P2",
            source_block: "S2",
          },
        ],
      },
    },
    parameters: [
      {
        job_id: 11,
        task_id: "formal_part1_load",
        job_status: "COMPLETED",
        fields: { library_id: "L1" },
      },
      {
        job_id: 12,
        task_id: "formal_part1_qc",
        job_status: "RUNNING",
        fields: { library_id: "L1" },
      },
    ],
    results: {
      scientific_status: {
        scientific_status: "FROZEN_PASS",
        calibration_status: "NOT_ESTABLISHED_FOR_THIS_ANALYSIS",
        associated: false,
        claims_limma: false,
        forecast_is_not_a_verdict: true,
        lodo_is_replication: false,
        holdout: "NOT_APPLICABLE",
        read_only: false,
        limits: [],
      },
      evidence: {
        lock: {
          mapping: { "0": "Monocyte", "1": "T_cell" },
        },
      },
      artifacts: [],
    },
    checks: [],
    logs: [],
  };
}

describe("workspace task console and reviewer store", () => {
  it("starts with empty reviewer and persists trimmed reviewer identity", () => {
    expect(readReviewer()).toBe("");
    saveReviewer("  TEST_REVIEWER  ");
    expect(readReviewer()).toBe("TEST_REVIEWER");
    saveReviewer("   ");
    expect(readReviewer()).toBe("");
    expect(todayIso()).toMatch(/^\d{4}-\d{2}-\d{2}$/);
  });

  it("extracts protocol libraries, locked cell types, and per-library job status", () => {
    const ws = sampleWorkspace();
    expect(extractProtocolLibraries(ws)).toHaveLength(2);
    expect(extractLockedCellTypes(ws)).toEqual(["Monocyte", "T_cell"]);
    expect(latestTaskStatus(ws, "formal_part1_load", "L1")).toBe("COMPLETED");
    expect(latestTaskStatus(ws, "formal_part1_load", "L2")).toBe("");
    expect(latestTaskStatus(ws, "formal_part1_qc", "L1")).toBe("RUNNING");
    expect(hasActiveFormalJobs(ws)).toBe(true);
  });

  it("renders Part 1 per-library controls, active job cancellation, and locked cell types", () => {
    const host = document.createElement("div");
    document.body.append(host);
    const root = createRoot(host);
    const render = (node: ReactNode) => act(() => root.render(node));
    hosts.push({ root, host });

    render(
      <WorkspaceTasks
        ws={sampleWorkspace()}
        onRefresh={() => undefined}
        onMessage={() => undefined}
      />,
    );

    expect(host.textContent).toContain("队列与运行中任务");
    expect(host.textContent).toContain("取消任务");
    expect(host.textContent).toContain("加载全部文库");
    expect(host.textContent).toContain("LOCKED");
    const options = [
      ...host.querySelectorAll("datalist#locked-types-7 option"),
    ].map((opt) => opt.getAttribute("value"));
    expect(options).toEqual(["Monocyte", "T_cell"]);
  });
});
