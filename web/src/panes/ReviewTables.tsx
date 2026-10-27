import { useEffect, useMemo, useRef, useState, type ReactNode } from "react";

import {
  errorText,
  loadReviewCenter,
  loadStageRuns,
  type ReviewCenter,
  type StageRunItem,
} from "../api/client";
import { chrome } from "../text/chrome";

type ReviewTab = "qc" | "markers";
const QC_QUANTILES = ["p5", "p25", "median", "p75", "p95"] as const;

const QC_METRICS = [
  { key: "total_counts", label: chrome.umiSummary, unit: "", digits: 0 },
  { key: "n_genes", label: chrome.genesSummary, unit: "", digits: 0 },
  { key: "pct_mt", label: chrome.mtSummary, unit: "%", digits: 1 },
  { key: "pct_hb", label: chrome.hbSummary, unit: "%", digits: 1 },
  { key: "pct_ribo", label: chrome.riboSummary, unit: "%", digits: 1 },
  { key: "pct_top50", label: chrome.top50Summary, unit: "%", digits: 1 },
  {
    key: "log10_genes_per_umi",
    label: chrome.complexitySummary,
    unit: "",
    digits: 3,
  },
  {
    key: "scrublet_doublet_score",
    label: chrome.scrubletSummary,
    unit: "",
    digits: 3,
  },
] as const;

const QC_QUANTILE_LABELS = ["P5", "P25", "P50", "P75", "P95"] as const;

export function ReviewTables() {
  const [runId, setRunId] = useState(0);
  const [runs, setRuns] = useState<StageRunItem[]>([]);
  const [center, setCenter] = useState<ReviewCenter | null>(null);
  const [tab, setTab] = useState<ReviewTab>("qc");
  const [cluster, setCluster] = useState("all");
  const [error, setError] = useState("");

  useEffect(() => {
    void loadStageRuns()
      .then((items) => {
        setRuns(items);
        setRunId((current) => current || items[0]?.id || 0);
      })
      .catch((reason: unknown) => setError(errorText(reason)));
    const updateContext = (event: Event) => {
      const detail = (event as CustomEvent<{ runId?: number }>).detail;
      if (detail?.runId) {
        setRunId(detail.runId);
        void loadReviewCenter(detail.runId)
          .then(setCenter)
          .catch((reason: unknown) => setError(errorText(reason)));
      }
    };
    window.addEventListener("stagecraft:review-context", updateContext);
    return () =>
      window.removeEventListener("stagecraft:review-context", updateContext);
  }, []);

  useEffect(() => {
    if (!runs.length || !runId) return;
    void loadReviewCenter(runId)
      .then(setCenter)
      .catch((reason: unknown) => setError(errorText(reason)));
  }, [runId, runs.length]);

  const selected = center?.review_tables.available
    ? center.review_tables
    : null;
  const clusters = useMemo(() => {
    if (!selected) return [];
    const ids = new Set<string>();
    selected.qc.forEach((row) => ids.add(String(row.cluster ?? "")));
    selected.markers.forEach((row) => ids.add(String(row.cluster ?? "")));
    return [...ids].filter(Boolean).sort(clusterSort);
  }, [selected]);
  const visibleMarkers = selected
    ? selected.markers.filter(
        (row) => cluster === "all" || String(row.cluster ?? "") === cluster,
      )
    : [];

  return (
    <div className="review-tables stack">
      <header className="row spread">
        <div>
          <h3>{chrome.reviewTables}</h3>
          <p className="hint">
            {chrome.reviewTablesNote}
            {center
              ? ` · ${chrome.activeRound} ${center.active_round} · ${chrome.resolutionLabel} ${center.selected_resolution || chrome.none}`
              : ""}
          </p>
        </div>
        <label className="run-selector">
          <span>{chrome.project}</span>
          <select
            value={runId}
            onChange={(event) => {
              setRunId(Number(event.target.value) || 1);
              setCluster("all");
            }}
          >
            {runs.map((run) => (
              <option key={run.id} value={run.id}>
                #{run.id} · {run.stage_status}
              </option>
            ))}
          </select>
        </label>
      </header>
      {error ? <p className="log-error">{error}</p> : null}
      {!selected ? (
        <p className="empty-state">
          {center?.review_tables_job_status === "FAILED"
            ? chrome.reviewTablesFailed
            : center?.review_state === "TABLES_PENDING"
              ? chrome.reviewTablesStarting
              : chrome.reviewTablesPending}
        </p>
      ) : (
        <>
          <div className="review-table-toolbar">
            <div
              className="tab-row"
              role="tablist"
              aria-label={chrome.reviewTables}
            >
              <button
                type="button"
                role="tab"
                aria-selected={tab === "qc"}
                className={tab === "qc" ? "on" : ""}
                onClick={() => setTab("qc")}
              >
                {chrome.qcSummary}
              </button>
              <button
                type="button"
                role="tab"
                aria-selected={tab === "markers"}
                className={tab === "markers" ? "on" : ""}
                onClick={() => setTab("markers")}
              >
                {chrome.markerEvidence}
              </button>
            </div>
            {tab === "markers" || tab === "qc" ? (
              <label className="table-select">
                <span>{chrome.reviewClusters}</span>
                <select
                  value={cluster}
                  onChange={(event) => setCluster(event.target.value)}
                >
                  <option value="all">{chrome.allClusters}</option>
                  {clusters.map((item) => (
                    <option key={item} value={item}>
                      {item}
                    </option>
                  ))}
                </select>
              </label>
            ) : null}
          </div>
          {tab === "qc" ? (
            <QcTable rows={selected.qc} cluster={cluster} />
          ) : (
            <MarkerTable rows={visibleMarkers} />
          )}
        </>
      )}
    </div>
  );
}

function QcTable({
  rows,
  cluster,
}: {
  rows: Record<string, unknown>[];
  cluster: string;
}) {
  const visibleRows = rows.filter(
    (row) => cluster === "all" || String(row.cluster ?? "") === cluster,
  );
  return (
    <div className="table-scroll">
      <table className="review-table review-qc-table">
        <thead>
          <tr>
            <th>{chrome.reviewClusters}</th>
            <th>{chrome.qcMetric}</th>
            <th>{chrome.qcQuantileRange}</th>
          </tr>
        </thead>
        <tbody>
          {visibleRows.flatMap((row) =>
            QC_METRICS.map((metric) => (
              <tr key={`${String(row.cluster)}-${metric.key}`}>
                <td>{String(row.cluster ?? "-")}</td>
                <td>
                  {metric.label}
                  {metric.key === "scrublet_doublet_score" &&
                  row.scrublet_status === "not_saved"
                    ? ` (${chrome.notSaved})`
                    : ""}
                </td>
                <td>
                  <QuantileSummary row={row} metric={metric} />
                </td>
              </tr>
            )),
          )}
        </tbody>
      </table>
      <p className="hint">{chrome.qcQuantileOrder}</p>
    </div>
  );
}

function QuantileSummary({
  row,
  metric,
}: {
  row: Record<string, unknown>;
  metric: (typeof QC_METRICS)[number];
}) {
  return (
    <div className="qc-quantile-summary">
      {QC_QUANTILES.map((quantile, index) => (
        <span key={quantile}>
          <small>{QC_QUANTILE_LABELS[index]}</small>
          <strong>{quantileValue(row, metric, quantile)}</strong>
        </span>
      ))}
    </div>
  );
}

function quantileValue(
  row: Record<string, unknown>,
  metric: (typeof QC_METRICS)[number],
  quantile: (typeof QC_QUANTILES)[number],
): string {
  const value =
    row[`${quantile}_${metric.key}`] ??
    (quantile === "median" ? row[`median_${metric.key}`] : undefined);
  if (typeof value !== "number" || !Number.isFinite(value)) return "-";
  return `${value.toFixed(metric.digits)}${metric.unit === "%" ? "%" : ""}`;
}

function MarkerTable({ rows }: { rows: Record<string, unknown>[] }) {
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

function clusterSort(left: string, right: string): number {
  const a = Number(left);
  const b = Number(right);
  return Number.isFinite(a) && Number.isFinite(b)
    ? a - b
    : left.localeCompare(right);
}
