// hygiene: state-machine review surface kept together for the human workflow.
import { useEffect, useRef, useState } from "react";

import {
  enqueueStageTask,
  errorText,
  loadReviewCenter,
  loadStageRuns,
  submitClusters,
  submitResolution,
  type ReviewCenter as Center,
  type StageRunItem,
} from "../api/client";
import {
  chrome,
  scientificLimitText,
  scientificStatusNote,
  scientificStatusTitle,
} from "../text/chrome";
import { Part3Review } from "./Part3Review";

type Row = { cluster: string; decision: "KEEP" | "DELETE"; name: string };

export function ReviewCenter() {
  const [runs, setRuns] = useState<StageRunItem[]>([]);
  const [runId, setRunId] = useState<number | null>(null);
  const [tab, setTab] = useState<"part1" | "part3">("part1");
  const [center, setCenter] = useState<Center | null>(null);
  const [rows, setRows] = useState<Row[]>([]);
  const [resolution, setResolution] = useState("");
  const [roundIndex, setRoundIndex] = useState(0);
  const [reviewState, setReviewState] = useState("CHOOSE_RESOLUTION");
  const [rationale, setRationale] = useState("");
  const [message, setMessage] = useState("");
  const [pollVersion, setPollVersion] = useState(0);
  const lastContext = useRef("");
  const activeRoundRef = useRef<number | null>(null);

  useEffect(() => {
    void loadStageRuns()
      .then((list) => {
        setRuns(list);
        setRunId(list[0]?.id ?? null);
      })
      .catch((reason: unknown) => setMessage(errorText(reason)));
  }, []);

  const changeRun = (nextRunId: number) => {
    activeRoundRef.current = null;
    lastContext.current = "";
    setRunId(nextRunId);
    setCenter(null);
    setRows([]);
    setResolution("");
    setRoundIndex(0);
    setReviewState("CHOOSE_RESOLUTION");
    setRationale("");
    setMessage("");
  };

  useEffect(() => {
    if (runId === null) {
      setCenter(null);
      return;
    }
    let stopped = false;
    let timer = 0;
    const refresh = () => {
      void loadReviewCenter(runId)
        .then((next) => {
          if (stopped) return;
          setCenter(next);
          setRoundIndex(next.active_round);
          setReviewState(next.review_state);
          if (activeRoundRef.current !== next.active_round) {
            activeRoundRef.current = next.active_round;
            setResolution(next.selected_resolution || "");
          } else if (next.selected_resolution) {
            setResolution(next.selected_resolution);
          }
          const saved = new Map(
            next.cluster_decisions.map((row) => [row.cluster, row]),
          );
          setRows(
            next.clusters.map((cluster) => {
              const prior = saved.get(cluster);
              return {
                cluster,
                decision: prior?.decision ?? "KEEP",
                name: prior?.name ?? "",
              };
            }),
          );
          const contextKey = [
            runId,
            next.active_round,
            next.selected_resolution,
            next.review_tables.available,
            next.review_tables_job_status,
          ].join(":");
          if (lastContext.current !== contextKey) {
            lastContext.current = contextKey;
            window.dispatchEvent(
              new CustomEvent("stagecraft:review-context", {
                detail: {
                  runId,
                  roundIndex: next.active_round,
                  resolution: next.selected_resolution,
                },
              }),
            );
          }
          if (
            !["COMPLETED", "FAILED", "CANCELLED"].includes(next.review_state) &&
            next.review_state !== "CHOOSE_RESOLUTION" &&
            next.review_state !== "REVIEW_CLUSTERS" &&
            !(
              next.review_state === "TABLES_PENDING" &&
              next.review_tables_job_status === "FAILED"
            )
          ) {
            timer = window.setTimeout(refresh, 2500);
          }
        })
        .catch((reason: unknown) => {
          if (!stopped) setMessage(errorText(reason));
        });
    };
    refresh();
    return () => {
      stopped = true;
      window.clearTimeout(timer);
    };
  }, [runId, pollVersion]);

  const deleted = rows.some((row) => row.decision === "DELETE");
  const committedDeletion = center?.cluster_decisions.some(
    (row) => row.decision === "DELETE",
  );
  const committedNames =
    center !== null &&
    center.cluster_decisions.length > 0 &&
    center.cluster_decisions.every((row) => row.name.trim());

  if (runs.length === 0) {
    return <p className="hint">{chrome.noAvailableReviews}</p>;
  }

  return (
    <div className="review-center stack">
      <header className="review-header">
        <div>
          <h2>{chrome.review}</h2>
        </div>
        <label className="run-selector">
          <span>{chrome.project}</span>
          <select
            value={runId ?? ""}
            onChange={(event) => changeRun(Number(event.target.value))}
          >
            {runs.map((item) => (
              <option key={item.id} value={item.id}>
                {item.id} · {item.stage_status}
              </option>
            ))}
          </select>
        </label>
      </header>
      <div className="tab-row" role="tablist">
        <button
          type="button"
          role="tab"
          aria-selected={tab === "part1"}
          className={tab === "part1" ? "on" : ""}
          onClick={() => setTab("part1")}
        >
          {chrome.part1ReviewTab}
        </button>
        <button
          type="button"
          role="tab"
          aria-selected={tab === "part3"}
          className={tab === "part3" ? "on" : ""}
          onClick={() => setTab("part3")}
        >
          {chrome.part3ReviewTab}
        </button>
      </div>

      {tab === "part3" ? (
        <Part3Review runId={runId} />
      ) : (
        <div className="stack">
          {center ? (
            <section
              className="review-status-panel"
              aria-label={chrome.scientificStatus}
            >
              <div className="section-title-row">
                <div className="scientific-status-copy">
                  <h3>
                    {scientificStatusTitle(
                      center.scientific_status.scientific_status,
                    )}
                  </h3>
                  <p>
                    {scientificStatusNote(
                      center.scientific_status.scientific_status,
                    )}
                  </p>
                </div>
                <span
                  className="status-code"
                  title={chrome.scientificStatusCode}
                >
                  {center.scientific_status.scientific_status}
                </span>
              </div>
              <ul className="limit-list">
                {center.scientific_status.limits
                  .filter((line) => scientificLimitText(line))
                  .map((line) => (
                    <li key={line}>{scientificLimitText(line)}</li>
                  ))}
              </ul>
            </section>
          ) : null}
          <section className="review-section">
            <div className="section-title-row">
              <div>
                <h3>{chrome.reviewResolutions}</h3>
                <p className="hint">{chrome.part1Stop1Title}</p>
              </div>
              <span className="selection-note">
                {resolution || chrome.none}
              </span>
            </div>
            {center && !center.selected_resolution ? (
              <div
                className="review-wall"
                aria-label={chrome.reviewResolutions}
              >
                {center.resolutions.map((tile) => (
                  <button
                    key={tile.resolution}
                    type="button"
                    className={resolution === tile.resolution ? "on" : ""}
                    onClick={() => setResolution(tile.resolution)}
                  >
                    {tile.resolution}
                    <span>
                      {tile.n_clusters} · {tile.min_cluster_size}-
                      {tile.max_cluster_size}
                    </span>
                  </button>
                ))}
              </div>
            ) : (
              <p className="selection-note">
                {chrome.activeRound}: {center?.active_round} ·{" "}
                {resolution || chrome.none}
              </p>
            )}
            {center && !center.selected_resolution ? (
              <>
                <label className="review-rationale">
                  {chrome.rationale}
                  <input
                    value={rationale}
                    onChange={(event) => setRationale(event.target.value)}
                    placeholder={chrome.rationalePlaceholder}
                  />
                </label>
                <button
                  type="button"
                  disabled={!resolution || !rationale.trim()}
                  onClick={() => {
                    if (!center || runId === null) return;
                    void submitResolution(runId, {
                      reviewer: "Lin",
                      decided_on: new Date().toISOString().slice(0, 10),
                      rationale,
                      evidence_hash: center.evidence_hash,
                      resolution,
                      blinding: center.quicklook_seen
                        ? "UNBLINDED_WITH_REASON"
                        : "BLIND",
                      round_index: roundIndex,
                    })
                      .then(() => setMessage(chrome.reviewTablesStarting))
                      .then(() => loadReviewCenter(runId))
                      .then((next) => {
                        setCenter(next);
                        setReviewState(next.review_state);
                        setPollVersion((version) => version + 1);
                      })
                      .catch((reason: unknown) =>
                        setMessage(errorText(reason)),
                      );
                  }}
                >
                  {chrome.chooseResolutionAndGenerate}
                </button>
              </>
            ) : null}
          </section>
          {reviewState === "TABLES_PENDING" ? (
            <div className="review-task-status">
              <p className="hint">
                {center?.review_tables_job_status === "FAILED"
                  ? chrome.reviewTablesFailed
                  : chrome.reviewTablesStarting}
              </p>
              {center?.review_tables_job_status === "FAILED" ? (
                <button
                  type="button"
                  onClick={() => {
                    if (
                      !center ||
                      runId === null ||
                      !center.selected_resolution
                    ) {
                      return;
                    }
                    void enqueueStageTask(runId, "formal_part1_review_tables", {
                      round_index: center.active_round,
                      resolution: center.selected_resolution,
                    })
                      .then(() => {
                        setMessage(chrome.reviewTablesStarting);
                        return loadReviewCenter(runId);
                      })
                      .then((next) => {
                        setCenter(next);
                        setReviewState(next.review_state);
                        setPollVersion((version) => version + 1);
                      })
                      .catch((reason: unknown) =>
                        setMessage(errorText(reason)),
                      );
                  }}
                >
                  {chrome.retryReviewTables}
                </button>
              ) : null}
            </div>
          ) : null}
          {center?.review_tables.available ? (
            <section className="review-section">
              <div className="section-title-row">
                <div>
                  <h3>{chrome.reviewClusters}</h3>
                  <p className="hint">
                    {chrome.part1Stop2Title} · {chrome.resolutionLabel}:{" "}
                    {resolution}
                  </p>
                </div>
                <span className="selection-note">{rows.length}</span>
              </div>
              {center.cluster_decisions.length &&
              reviewState !== "NAMES_PENDING" ? (
                <p className="hint">
                  {deleted
                    ? chrome.roundRecomputeStarting
                    : chrome.part1LockStarting}
                </p>
              ) : null}
              <table className="review-table">
                <thead>
                  <tr>
                    <th>{chrome.reviewClusters}</th>
                    <th>{chrome.keep}</th>
                    {reviewState === "NAMES_PENDING" && !deleted ? (
                      <th>{chrome.name}</th>
                    ) : null}
                  </tr>
                </thead>
                <tbody>
                  {rows.map((row) => (
                    <tr key={row.cluster}>
                      <td>{row.cluster}</td>
                      <td>
                        <select
                          value={row.decision}
                          disabled={center.cluster_decisions.length > 0}
                          onChange={(event) => {
                            const decision =
                              event.target.value === "DELETE"
                                ? "DELETE"
                                : "KEEP";
                            setRows((current) =>
                              current.map((item) =>
                                item.cluster === row.cluster
                                  ? { ...item, decision }
                                  : item,
                              ),
                            );
                          }}
                        >
                          <option value="KEEP">{chrome.keep}</option>
                          <option value="DELETE">{chrome.delete}</option>
                        </select>
                      </td>
                      {reviewState === "NAMES_PENDING" && !deleted ? (
                        <td>
                          <input
                            value={deleted ? "" : row.name}
                            disabled={
                              deleted ||
                              row.decision === "DELETE" ||
                              reviewState !== "NAMES_PENDING"
                            }
                            onChange={(event) =>
                              setRows((current) =>
                                current.map((item) =>
                                  item.cluster === row.cluster
                                    ? { ...item, name: event.target.value }
                                    : item,
                                ),
                              )
                            }
                          />
                        </td>
                      ) : null}
                    </tr>
                  ))}
                </tbody>
              </table>
              {reviewState === "REVIEW_CLUSTERS" ||
              reviewState === "NAMES_PENDING" ? (
                <label className="review-rationale">
                  {chrome.rationale}
                  <input
                    placeholder={chrome.rationalePlaceholder}
                    value={rationale}
                    onChange={(event) => setRationale(event.target.value)}
                  />
                </label>
              ) : null}
              {reviewState === "REVIEW_CLUSTERS" ||
              reviewState === "NAMES_PENDING" ? (
                <p className="hint">
                  {center.quicklook_seen
                    ? chrome.unblindedReason
                    : chrome.blinding}
                </p>
              ) : null}
              {reviewState === "REVIEW_CLUSTERS" ||
              reviewState === "NAMES_PENDING" ? (
                <button
                  type="button"
                  disabled={
                    !rationale.trim() ||
                    (reviewState === "NAMES_PENDING" &&
                      rows.some((row) => !row.name.trim()))
                  }
                  onClick={() => {
                    if (runId === null) return;
                    void submitClusters(runId, {
                      blinding: center.quicklook_seen
                        ? "UNBLINDED_WITH_REASON"
                        : "BLIND",
                      round_index: roundIndex,
                      rows: rows.map((row) => ({
                        cluster: row.cluster,
                        decision: row.decision,
                        rationale,
                        reviewer: "Lin",
                        decided_on: new Date().toISOString().slice(0, 10),
                        name: deleted ? "" : row.name,
                      })),
                    })
                      .then((result) => {
                        const job = (result as { next_job_id?: number })
                          .next_job_id;
                        setMessage(
                          deleted
                            ? chrome.roundRecomputeStarting
                            : chrome.part1LockStarting,
                        );
                        return loadReviewCenter(runId)
                          .then((next) => {
                            setCenter(next);
                            setRoundIndex(next.active_round);
                            setResolution(next.selected_resolution || "");
                            setReviewState(next.review_state);
                            setPollVersion((version) => version + 1);
                          })
                          .then(() => job);
                      })
                      .catch((reason: unknown) =>
                        setMessage(errorText(reason)),
                      );
                  }}
                >
                  {deleted
                    ? chrome.submitDeletesAndRecluster
                    : reviewState === "NAMES_PENDING"
                      ? chrome.submitNamesAndLock
                      : chrome.submitClusterDecisions}
                </button>
              ) : null}
            </section>
          ) : null}
          {reviewState === "FAILED" && committedDeletion ? (
            <div className="review-task-status">
              <p className="hint">{chrome.roundRecomputeFailed}</p>
              <button
                type="button"
                onClick={() => {
                  if (runId === null) return;
                  void enqueueStageTask(runId, "formal_part1_round", {
                    round_index: roundIndex + 1,
                  })
                    .then(() => loadReviewCenter(runId))
                    .then((next) => {
                      setCenter(next);
                      setReviewState(next.review_state);
                      setPollVersion((version) => version + 1);
                    })
                    .catch((reason: unknown) => setMessage(errorText(reason)));
                }}
              >
                {chrome.retryRound}
              </button>
            </div>
          ) : null}
          {reviewState === "FAILED" && committedNames ? (
            <div className="review-task-status">
              <p className="hint">{chrome.part1LockFailed}</p>
              <button
                type="button"
                onClick={() => {
                  if (runId === null) return;
                  void enqueueStageTask(runId, "formal_part1_lock")
                    .then(() => loadReviewCenter(runId))
                    .then((next) => {
                      setCenter(next);
                      setReviewState(next.review_state);
                      setPollVersion((version) => version + 1);
                    })
                    .catch((reason: unknown) => setMessage(errorText(reason)));
                }}
              >
                {chrome.retryPart1Lock}
              </button>
            </div>
          ) : null}
          {reviewState === "RECLUSTER_PENDING" ||
          reviewState === "QUEUED" ||
          reviewState === "RUNNING" ? (
            <p className="hint">{chrome.roundRecomputeStarting}</p>
          ) : null}
          {message ? <p className="hint">{message}</p> : null}
        </div>
      )}
    </div>
  );
}
