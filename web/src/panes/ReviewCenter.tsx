import { useEffect, useState } from "react";

import {
  errorText,
  loadReviewCenter,
  loadStageRuns,
  submitClusters,
  submitResolution,
  type ReviewCenter as Center,
  type StageRunItem,
} from "../api/client";
import { chrome } from "../text/chrome";

type Row = { cluster: string; decision: "KEEP" | "DELETE"; name: string };

export function ReviewCenter() {
  const [runs, setRuns] = useState<StageRunItem[]>([]);
  const [runId, setRunId] = useState<number | null>(null);
  const [center, setCenter] = useState<Center | null>(null);
  const [rows, setRows] = useState<Row[]>([]);
  const [resolution, setResolution] = useState("");
  const [rationale, setRationale] = useState("");
  const [message, setMessage] = useState("");

  useEffect(() => {
    void loadStageRuns()
      .then((list) => {
        setRuns(list);
        setRunId(list[0]?.id ?? null);
      })
      .catch((reason: unknown) => setMessage(errorText(reason)));
  }, []);

  useEffect(() => {
    if (runId === null) {
      setCenter(null);
      return;
    }
    void loadReviewCenter(runId)
      .then((next) => {
        setCenter(next);
        setRows(
          next.clusters.map((cluster) => ({
            cluster,
            decision: "KEEP",
            name: "",
          })),
        );
        setResolution(next.resolutions[0]?.resolution ?? "");
      })
      .catch((reason: unknown) => setMessage(errorText(reason)));
  }, [runId]);

  const deleted = rows.some((row) => row.decision === "DELETE");

  if (runs.length === 0) {
    return <p className="hint">{chrome.formalNote}</p>;
  }

  return (
    <form
      className="stack"
      onSubmit={(event) => {
        event.preventDefault();
        if (!center || runId === null) return;
        const blinding = center.quicklook_seen
          ? "UNBLINDED_WITH_REASON"
          : "BLIND";
        void submitResolution(runId, {
          reviewer: "Lin",
          decided_on: "2026-10-01",
          rationale,
          evidence_hash: center.evidence_hash,
          resolution,
          blinding,
        })
          .then(() =>
            submitClusters(runId, {
              blinding,
              rows: rows.map((row) => ({
                cluster: row.cluster,
                decision: row.decision,
                rationale,
                reviewer: "Lin",
                decided_on: "2026-10-01",
                name: deleted ? "" : row.name,
              })),
            }),
          )
          .then(() => setMessage(chrome.submitReview))
          .catch((reason: unknown) => setMessage(errorText(reason)));
      }}
    >
      <label>
        {chrome.formal}
        <select
          value={runId ?? ""}
          onChange={(event) => setRunId(Number(event.target.value))}
        >
          {runs.map((item) => (
            <option key={item.id} value={item.id}>
              {item.id} · {item.stage_status}
            </option>
          ))}
        </select>
      </label>
      {center ? (
        <section aria-label={chrome.scientificStatus}>
          <h2>{chrome.scientificStatus}</h2>
          <p>{center.scientific_status.scientific_status}</p>
          <ul>
            {center.scientific_status.limits.map((line) => (
              <li key={line}>{line}</li>
            ))}
          </ul>
        </section>
      ) : null}
      <div className="review-wall" aria-label={chrome.reviewResolutions}>
        {center?.resolutions.map((tile) => (
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
      <table>
        <thead>
          <tr>
            <th>{chrome.reviewClusters}</th>
            <th>{chrome.keep}</th>
            <th>{chrome.name}</th>
          </tr>
        </thead>
        <tbody>
          {rows.map((row) => (
            <tr key={row.cluster}>
              <td>{row.cluster}</td>
              <td>
                <select
                  value={row.decision}
                  onChange={(event) => {
                    const decision =
                      event.target.value === "DELETE" ? "DELETE" : "KEEP";
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
              <td>
                <input
                  value={deleted ? "" : row.name}
                  disabled={deleted || row.decision === "DELETE"}
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
            </tr>
          ))}
        </tbody>
      </table>
      <label>
        {chrome.reviewResolutions}
        <input
          value={rationale}
          onChange={(event) => setRationale(event.target.value)}
        />
      </label>
      <p className="hint">
        {center?.quicklook_seen ? "UNBLINDED_WITH_REASON" : chrome.blinding}
      </p>
      <button type="submit">{chrome.submitReview}</button>
      {message ? <p className="hint">{message}</p> : null}
    </form>
  );
}
