import { stageArtifactUrl, type GalleryFigureItem } from "../api/client";
import { chrome } from "../text/chrome";

export function GalleryCard({
  item,
  runId,
  onFocus,
}: {
  item: GalleryFigureItem;
  runId: number;
  onFocus: (item: GalleryFigureItem) => void;
}) {
  if (item.status === "NOT_ESTIMABLE") {
    return (
      <div className="gallery-card-not-estimable">
        <div className="row spread" style={{ marginBottom: "6px" }}>
          <span className="badge badge-warning">{item.panel_id}</span>
          <span
            style={{
              fontWeight: "700",
              color: "var(--amber-primary)",
              fontSize: "12px",
            }}
          >
            NOT_ESTIMABLE
          </span>
        </div>
        <h4 style={{ margin: "4px 0 6px 0", fontSize: "14px" }}>
          {item.title}
        </h4>
        <p
          style={{
            fontSize: "12px",
            color: "var(--text-muted)",
            margin: "0 0 8px 0",
          }}
        >
          {item.caption}
        </p>
        {item.reasons.length > 0 ? (
          <div
            style={{
              display: "flex",
              flexWrap: "wrap",
              gap: "4px",
              marginBottom: "8px",
            }}
          >
            {item.reasons.map((r, i) => (
              <span key={i} className="badge" style={{ fontSize: "11px" }}>
                {r}
              </span>
            ))}
          </div>
        ) : null}
        {item.source_data ? (
          <a
            href={stageArtifactUrl(runId, item.source_data)}
            target="_blank"
            rel="noreferrer"
            style={{ fontSize: "12px" }}
          >
            {chrome.downloadSourceData} (CSV)
          </a>
        ) : null}
      </div>
    );
  }

  return (
    <div className="thumb" style={{ cursor: "default", margin: 0 }}>
      <div
        className="thumb-img-wrap"
        style={{ cursor: "pointer" }}
        onClick={() => onFocus(item)}
      >
        {item.format_png || item.format_svg ? (
          <img
            src={stageArtifactUrl(
              runId,
              item.format_png || item.format_svg || "",
            )}
            alt={item.title}
            loading="lazy"
          />
        ) : (
          <div style={{ height: "140px", background: "#f1f5f9" }} />
        )}
      </div>
      <div className="thumb-meta" style={{ marginTop: "6px" }}>
        <span className="badge">{item.panel_id}</span>
        <span
          style={{
            fontWeight: "600",
            fontSize: "13px",
            overflow: "hidden",
            textOverflow: "ellipsis",
          }}
        >
          {item.title}
        </span>
      </div>
      <p
        style={{
          fontSize: "11px",
          color: "var(--text-muted)",
          margin: "4px 0",
        }}
      >
        {item.caption}
      </p>
      <div
        className="row"
        style={{ gap: "6px", fontSize: "11px", marginTop: "4px" }}
      >
        <button
          type="button"
          onClick={() => onFocus(item)}
          style={{ padding: "2px 6px" }}
        >
          {chrome.preview}
        </button>
        {item.format_svg ? (
          <a
            href={stageArtifactUrl(runId, item.format_svg)}
            target="_blank"
            rel="noreferrer"
          >
            SVG
          </a>
        ) : null}
        {item.format_pdf ? (
          <a
            href={stageArtifactUrl(runId, item.format_pdf)}
            target="_blank"
            rel="noreferrer"
          >
            PDF
          </a>
        ) : null}
        {item.source_data ? (
          <a
            href={stageArtifactUrl(runId, item.source_data)}
            target="_blank"
            rel="noreferrer"
          >
            {chrome.downloadSourceData}
          </a>
        ) : null}
        {item.parameters ? (
          <a
            href={stageArtifactUrl(runId, item.parameters)}
            target="_blank"
            rel="noreferrer"
          >
            {chrome.viewParameters}
          </a>
        ) : null}
      </div>
    </div>
  );
}
