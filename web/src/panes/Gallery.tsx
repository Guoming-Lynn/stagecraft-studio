import { useEffect, useState } from "react";

import {
  errorText,
  loadStageGallery,
  loadStageRuns,
  stageArtifactUrl,
  type GalleryFigureItem,
  type StageGalleryView,
  type StageRunItem,
} from "../api/client";
import { chrome } from "../text/chrome";
import { GalleryCard } from "./GalleryCard";

export function Gallery() {
  const [runs, setRuns] = useState<StageRunItem[]>([]);
  const [runId, setRunId] = useState<number | null>(null);
  const [gallery, setGallery] = useState<StageGalleryView | null>(null);
  const [filterPart, setFilterPart] = useState<string>("ALL");
  const [focus, setFocus] = useState<GalleryFigureItem | null>(null);
  const [message, setMessage] = useState("");

  useEffect(() => {
    void loadStageRuns()
      .then((list) => {
        setRuns(list);
        setRunId(list[0]?.id ?? null);
      })
      .catch((err: unknown) => setMessage(errorText(err)));
  }, []);

  useEffect(() => {
    if (runId === null) {
      setGallery(null);
      return;
    }
    void loadStageGallery(runId)
      .then(setGallery)
      .catch((err: unknown) => setMessage(errorText(err)));
  }, [runId]);

  if (runs.length === 0) {
    return (
      <div className="empty-state">
        <p>{chrome.formalNote}</p>
      </div>
    );
  }

  const items = gallery?.figures ?? [];
  const filtered = items.filter((f) => {
    if (filterPart === "ALL") return true;
    if (filterPart === "NOT_ESTIMABLE") return f.status === "NOT_ESTIMABLE";
    return f.stage_part === filterPart;
  });

  return (
    <div className="stack">
      {message ? <p className="log-error">{message}</p> : null}
      <div
        className="row spread"
        style={{ alignItems: "center", marginBottom: "8px" }}
      >
        <div className="row" style={{ alignItems: "center", gap: "8px" }}>
          <label htmlFor="gallery-run-select">
            <strong>Stage Run:</strong>
          </label>
          <select
            id="gallery-run-select"
            value={runId ?? ""}
            onChange={(e) => setRunId(Number(e.target.value))}
          >
            {runs.map((r) => (
              <option key={r.id} value={r.id}>
                Stage Run #{r.id} ({r.stage_status})
              </option>
            ))}
          </select>
        </div>
        {gallery ? (
          <div className="row" style={{ gap: "6px", fontSize: "12px" }}>
            <span className="badge">
              总图数: {gallery.total_figures} (可用: {gallery.available_count})
            </span>
            {gallery.not_estimable_count > 0 ? (
              <span className="badge badge-warning">
                NOT_ESTIMABLE: {gallery.not_estimable_count}
              </span>
            ) : null}
          </div>
        ) : null}
      </div>

      {gallery ? (
        <div
          className="scientific-banner"
          style={{
            border: "1px solid var(--border-strong, #cbd5e1)",
            padding: "8px 12px",
            borderRadius: "6px",
            marginBottom: "12px",
            background: "var(--bg-surface, #f8fafc)",
          }}
        >
          <div className="row spread" style={{ alignItems: "center" }}>
            <div className="row" style={{ gap: "8px", alignItems: "center" }}>
              <strong>科学边界：</strong>
              <span className="badge badge-warning">
                校准状态: {gallery.scientific_status.calibration_status}
              </span>
              <span className="badge">
                关联断言:{" "}
                {gallery.scientific_status.associated
                  ? "true"
                  : "false (未建立)"}
              </span>
              <span className="badge">
                证据上限: {gallery.scientific_status.evidence_ceiling}
              </span>
            </div>
          </div>
          {gallery.not_estimable_count > 0 ? (
            <p
              style={{
                margin: "6px 0 0 0",
                fontSize: "12px",
                color: "var(--amber-primary, #b45309)",
              }}
            >
              ⚠️ 保留 {gallery.not_estimable_count} 个不可估计 (NOT_ESTIMABLE)
              槽位：按科学规范保留，不为排版美观而隐匿失败项。
            </p>
          ) : null}
        </div>
      ) : null}

      <div
        className="row"
        style={{ gap: "8px", marginBottom: "12px", flexWrap: "wrap" }}
      >
        {[
          { key: "ALL", label: `全部 (${items.length})` },
          { key: "Part 1", label: "Part 1 网格" },
          { key: "Part 2", label: "Part 2 描述" },
          { key: "Part 4", label: "Part 4 可识别性" },
          { key: "Part 5", label: "Part 5 拟合" },
          {
            key: "NOT_ESTIMABLE",
            label: `仅看不可估计 (${gallery?.not_estimable_count ?? 0})`,
          },
        ].map((f) => (
          <button
            key={f.key}
            type="button"
            className={filterPart === f.key ? "on" : ""}
            onClick={() => setFilterPart(f.key)}
            style={{ fontSize: "12px", padding: "4px 8px" }}
          >
            {f.label}
          </button>
        ))}
      </div>

      <div
        style={{
          display: "grid",
          gridTemplateColumns: "repeat(auto-fill, minmax(280px, 1fr))",
          gap: "16px",
        }}
      >
        {runId
          ? filtered.map((item) => (
              <GalleryCard
                key={item.id}
                item={item}
                runId={runId}
                onFocus={setFocus}
              />
            ))
          : null}
      </div>

      {focus && runId ? (
        <dialog open className="lightbox" style={{ maxWidth: "800px" }}>
          <div className="lightbox-top">
            <strong>{focus.title}</strong>
            <button type="button" onClick={() => setFocus(null)}>
              {chrome.close}
            </button>
          </div>
          <div style={{ textAlign: "center", margin: "12px 0" }}>
            <img
              src={stageArtifactUrl(
                runId,
                focus.format_png || focus.format_svg || "",
              )}
              alt={focus.title}
              style={{ maxHeight: "65vh", objectFit: "contain" }}
            />
          </div>
          <div className="row spread" style={{ fontSize: "12px" }}>
            <span style={{ color: "var(--text-muted)" }}>
              Hash: {focus.content_hash || "n/a"}
            </span>
            <div className="row" style={{ gap: "8px" }}>
              {focus.format_svg ? (
                <a
                  href={stageArtifactUrl(runId, focus.format_svg)}
                  target="_blank"
                  rel="noreferrer"
                >
                  下载 SVG
                </a>
              ) : null}
              {focus.format_pdf ? (
                <a
                  href={stageArtifactUrl(runId, focus.format_pdf)}
                  target="_blank"
                  rel="noreferrer"
                >
                  下载 PDF
                </a>
              ) : null}
              {focus.source_data ? (
                <a
                  href={stageArtifactUrl(runId, focus.source_data)}
                  target="_blank"
                  rel="noreferrer"
                >
                  下载 Source Data
                </a>
              ) : null}
              {focus.parameters ? (
                <a
                  href={stageArtifactUrl(runId, focus.parameters)}
                  target="_blank"
                  rel="noreferrer"
                >
                  查看参数
                </a>
              ) : null}
            </div>
          </div>
        </dialog>
      ) : null}
    </div>
  );
}
