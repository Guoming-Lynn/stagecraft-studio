import { useEffect, useRef, useState, type ReactNode } from "react";

import { chrome } from "../text/chrome";

export function MarkerTable({ rows }: { rows: Record<string, unknown>[] }) {
  return (
    <SyncedTableScroll>
      <table className="review-table review-marker-table">
        <thead>
          <tr>
            <th>{chrome.reviewClusters}</th>
            <th>{chrome.rank}</th>
            <th>{chrome.gene}</th>
            <th>{chrome.logFoldChange}</th>
            <th>{chrome.pctInCluster}</th>
            <th>{chrome.pctOutCluster}</th>
            <th>{chrome.pctDelta}</th>
            <th>{chrome.markerQuality}</th>
            <th>{chrome.qualityBasis}</th>
          </tr>
        </thead>
        <tbody>
          {rows.map((row, index) => (
            <tr
              key={`${String(row.cluster)}-${String(row.rank)}-${String(row.gene)}-${index}`}
            >
              <td>{String(row.cluster ?? "-")}</td>
              <td>{numberValue(row, "rank")}</td>
              <td className="marker-gene">{String(row.gene ?? "-")}</td>
              <td>{numberValue(row, "logfoldchange")}</td>
              <td>{numberValue(row, "pct_in", true)} %</td>
              <td>{numberValue(row, "pct_out", true)} %</td>
              <td>{numberValue(row, "pct_delta", true)} %</td>
              <td>
                <span
                  className={`marker-quality marker-quality-${String(row.marker_quality ?? "").toLowerCase()}`}
                >
                  {String(row.marker_quality ?? "-")}
                </span>
              </td>
              <td className="quality-basis">
                {String(row.quality_basis ?? "-")}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
      <p className="hint">{chrome.markerQualityDisclaimer}</p>
    </SyncedTableScroll>
  );
}

function SyncedTableScroll({ children }: { children: ReactNode }) {
  const shellRef = useRef<HTMLDivElement>(null);
  const railRef = useRef<HTMLDivElement>(null);
  const spacerRef = useRef<HTMLDivElement>(null);
  const viewportRef = useRef<HTMLDivElement>(null);
  const contentRef = useRef<HTMLDivElement>(null);
  const [hasOverflow, setHasOverflow] = useState(false);

  useEffect(() => {
    const shell = shellRef.current;
    const rail = railRef.current;
    const spacer = spacerRef.current;
    const viewport = viewportRef.current;
    const content = contentRef.current;
    if (!shell || !viewport || !content) return;

    const measure = () => {
      const width = Math.max(
        content.scrollWidth,
        content.getBoundingClientRect().width,
      );
      if (spacer && rail) {
        spacer.style.width = `${rail.clientWidth + width - viewport.clientWidth}px`;
      }
      setHasOverflow(width > viewport.clientWidth + 1);
    };
    const syncRail = () => {
      if (rail && rail.scrollLeft !== viewport.scrollLeft) {
        rail.scrollLeft = viewport.scrollLeft;
      }
    };
    const syncViewport = () => {
      if (rail && viewport.scrollLeft !== rail.scrollLeft) {
        viewport.scrollLeft = rail.scrollLeft;
      }
    };

    measure();
    rail?.addEventListener("scroll", syncViewport, { passive: true });
    viewport.addEventListener("scroll", syncRail, { passive: true });
    const observer = new ResizeObserver(measure);
    observer.observe(shell);
    observer.observe(viewport);
    observer.observe(content);
    return () => {
      rail?.removeEventListener("scroll", syncViewport);
      viewport.removeEventListener("scroll", syncRail);
      observer.disconnect();
    };
  }, [children, hasOverflow]);

  return (
    <div className="marker-table-shell" ref={shellRef}>
      {hasOverflow ? (
        <div
          aria-label={chrome.horizontalScrollTable}
          className="marker-table-scroll-rail"
          ref={railRef}
          role="region"
          tabIndex={0}
          title={chrome.horizontalScrollTable}
        >
          <div aria-hidden="true" ref={spacerRef} />
        </div>
      ) : null}
      <div className="marker-table-viewport" ref={viewportRef}>
        <div className="marker-table-content" ref={contentRef}>
          {children}
        </div>
      </div>
    </div>
  );
}

function numberValue(
  row: Record<string, unknown>,
  key: string,
  fraction = false,
): string {
  const value = row[key];
  if (typeof value !== "number" || !Number.isFinite(value)) return "-";
  const normalized = fraction ? value * 100 : value;
  return normalized.toFixed(fraction || key.includes("pct") ? 1 : 0);
}
