import { act, type ReactNode } from "react";
import { createRoot, type Root } from "react-dom/client";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import type { GalleryFigureItem } from "../src/api/client";
import { Gallery } from "../src/panes/Gallery";
import { GalleryCard } from "../src/panes/GalleryCard";

const hosts: { root: Root; host: HTMLElement }[] = [];

beforeEach(() => {
  vi.spyOn(globalThis, "fetch").mockImplementation(async (input) => {
    const url = String(input);
    if (url.includes("/api/stage-runs")) {
      return new Response(JSON.stringify([]), {
        status: 200,
        headers: { "Content-Type": "application/json" },
      });
    }
    return new Response(JSON.stringify({}), {
      status: 200,
      headers: { "Content-Type": "application/json" },
    });
  });
});

afterEach(() => {
  vi.restoreAllMocks();
  for (const item of hosts) {
    act(() => item.root.unmount());
    item.host.remove();
  }
  hosts.length = 0;
});

function mount(node: ReactNode): HTMLElement {
  const host = document.createElement("div");
  document.body.append(host);
  const root = createRoot(host);
  act(() => root.render(node));
  hosts.push({ root, host });
  return host;
}

describe("Gallery components", () => {
  it("renders available figure card with title and format links", () => {
    const item: GalleryFigureItem = {
      id: "formal_part2_figures/F02_01_KRAS_umap_counts",
      task_id: "formal_part2_figures",
      title: "F02_01: KRAS umap counts",
      stage_part: "Part 2",
      panel_id: "F02_01",
      status: "AVAILABLE",
      format_png: "formal_part2_figures/F02_01_KRAS_umap_counts.png",
      format_svg: "formal_part2_figures/F02_01_KRAS_umap_counts.svg",
      format_pdf: "formal_part2_figures/F02_01_KRAS_umap_counts.pdf",
      source_data:
        "formal_part2_figures/source_data/F02_01_KRAS_umap_counts.csv",
      parameters:
        "formal_part2_figures/F02_01_KRAS_umap_counts.parameters.json",
      caption: "Part 2 single-cell target survey on locked UMAP coordinates.",
      reasons: [],
      content_hash: "abcd1234",
    };

    let focused: GalleryFigureItem | null = null;
    const host = mount(
      <GalleryCard
        item={item}
        runId={1}
        onFocus={(f) => {
          focused = f;
        }}
      />,
    );

    expect(host.textContent).toContain("F02_01");
    expect(host.textContent).toContain("KRAS umap counts");
    expect(host.textContent).toContain("大图");
    expect(host.textContent).toContain("SVG");
    expect(host.textContent).toContain("PDF");
    expect(host.textContent).toContain("数据");
    expect(host.textContent).toContain("参数");

    const img = host.querySelector("img");
    expect(img).not.toBeNull();
    expect(img?.getAttribute("src")).toContain("formal_part2_figures");

    const btn = host.querySelector("button");
    act(() => btn?.click());
    expect(focused).toBe(item);
  });

  it("renders NOT_ESTIMABLE figure card with distinct status and reasons", () => {
    const item: GalleryFigureItem = {
      id: "not_estimable_part5_Basal",
      task_id: "formal_part5_prepare",
      title: "Part 5 Model Fit: Basal (NOT_ESTIMABLE)",
      stage_part: "Part 5",
      panel_id: "F05_NOT_ESTIMABLE",
      status: "NOT_ESTIMABLE",
      format_png: null,
      format_svg: null,
      format_pdf: null,
      source_data: "formal_part5_prepare/eligibility.csv",
      parameters: null,
      caption: "The donor-level association model is not estimable.",
      reasons: ["LOW_N", "NO_EXPOSURE_RANGE"],
      content_hash: "",
    };

    const host = mount(
      <GalleryCard item={item} runId={1} onFocus={() => undefined} />,
    );

    expect(host.textContent).toContain("NOT_ESTIMABLE");
    expect(host.textContent).toContain("Part 5 Model Fit: Basal");
    expect(host.textContent).toContain("LOW_N");
    expect(host.textContent).toContain("NO_EXPOSURE_RANGE");
    expect(host.textContent).toContain("下载资格数据 (CSV)");
  });

  it("renders empty state when there are no formal stage runs", () => {
    const host = mount(<Gallery />);
    expect(host.textContent).toContain("正式分析还没有待审阅的运行");
  });
});
