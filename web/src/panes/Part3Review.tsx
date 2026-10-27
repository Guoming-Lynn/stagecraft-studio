import { useEffect, useState } from "react";

import {
  errorText,
  loadPart3Center,
  submitPart3Clusters,
  submitPart3Names,
  submitPart3Resolution,
  type Part3CenterView,
} from "../api/client";
import { chrome } from "../text/chrome";
import { Stop2Table, Stop3Table, type S2Row, type S3Row } from "./Part3Tables";

export function Part3Review({ runId }: { runId: number | null }) {
  const [center, setCenter] = useState<Part3CenterView | null>(null);
  const [resolution, setResolution] = useState("");
  const [rationale, setRationale] = useState("");
  const [stop2Rows, setStop2Rows] = useState<S2Row[]>([]);
  const [stop3Rows, setStop3Rows] = useState<S3Row[]>([]);
  const [message, setMessage] = useState("");

  const refresh = (id: number) => {
    loadPart3Center(id)
      .then((data) => {
        setCenter(data);
        if (data.resolutions.length > 0 && !resolution) {
          setResolution(data.resolutions[0]?.resolution ?? "");
        }
        setStop2Rows(
          data.clusters.map((c) => ({
            cluster: c,
            decision: "KEEP",
            rationale: "",
          })),
        );
        const kept = data.current_clusters?.rows
          ? data.current_clusters.rows
              .filter((r) => r.decision === "KEEP")
              .map((r) => r.cluster)
          : data.clusters;
        setStop3Rows(
          kept.map((c) => ({ cluster: c, name: "", rationale: "" })),
        );
      })
      .catch((err: unknown) => setMessage(errorText(err)));
  };

  useEffect(() => {
    if (runId !== null) refresh(runId);
    else setCenter(null);
  }, [runId]);

  if (!center) return <p className="hint">{chrome.part3Awaiting}</p>;

  const active = center.active_stop_point;
  const blinding = center.quicklook_seen ? "UNBLINDED_WITH_REASON" : "BLIND";

  const postAction = (fn: () => Promise<unknown>, label: string) => {
    fn()
      .then(() => {
        setMessage(label);
        if (runId !== null) refresh(runId);
      })
      .catch((e: unknown) => setMessage(errorText(e)));
  };

  const submitStop1 = (e: React.FormEvent) => {
    e.preventDefault();
    if (runId === null) return;
    postAction(
      () =>
        submitPart3Resolution(runId, {
          reviewer: "Lin",
          decided_on: "2026-10-01",
          rationale: rationale || "Resolution",
          evidence_hash: center.evidence_hash,
          resolution,
          blinding,
        }),
      chrome.part3Stop1Done,
    );
  };

  const submitStop2 = (e: React.FormEvent) => {
    e.preventDefault();
    if (runId === null) return;
    postAction(
      () =>
        submitPart3Clusters(runId, {
          blinding,
          rows: stop2Rows.map((r) => ({
            ...r,
            rationale: r.rationale || "Decision",
            reviewer: "Lin",
            decided_on: "2026-10-01",
          })),
        }),
      chrome.part3Stop2Done,
    );
  };

  const submitStop3 = (e: React.FormEvent) => {
    e.preventDefault();
    if (runId === null) return;
    postAction(
      () =>
        submitPart3Names(runId, {
          blinding,
          rows: stop3Rows.map((r) => ({
            ...r,
            rationale: r.rationale || "Annotation",
            reviewer: "Lin",
            decided_on: "2026-10-01",
          })),
        }),
      chrome.part3Stop3Done,
    );
  };

  return (
    <div className="stack" aria-label={chrome.part3ReviewTab}>
      <header>
        <h3>{chrome.part3ReviewTab}</h3>
        <p className="hint">
          {active === "AWAITING_RECLUSTER" && chrome.part3Awaiting}
          {active === "STOP1_RESOLUTION" && chrome.part3Stop1Title}
          {active === "STOP2_CLUSTERS" && chrome.part3Stop2Title}
          {active === "CLEANUP_REQUIRED" && chrome.part3CleanupRequired}
          {active === "STOP3_NAMES" && chrome.part3Stop3Title}
          {active === "COMPLETED" && chrome.part3Completed}
        </p>
      </header>

      <section className="stack">
        <h4>{chrome.part3Stop1Title}</h4>
        <div className="review-wall">
          {center.resolutions.map((t) => (
            <button
              key={t.resolution}
              type="button"
              className={resolution === t.resolution ? "on" : ""}
              disabled={active !== "STOP1_RESOLUTION"}
              onClick={() => setResolution(t.resolution)}
            >
              {t.resolution}
              <span>
                {t.n_clusters} · {t.min_cluster_size}-{t.max_cluster_size}
              </span>
            </button>
          ))}
        </div>
        {active === "STOP1_RESOLUTION" && (
          <form onSubmit={submitStop1}>
            <label>
              {chrome.reviewResolutions}
              <input
                value={rationale}
                placeholder={chrome.rationale}
                onChange={(e) => setRationale(e.target.value)}
              />
            </label>
            <button type="submit">{chrome.submitPart3Stop1}</button>
          </form>
        )}
      </section>

      {(active === "STOP2_CLUSTERS" ||
        active === "CLEANUP_REQUIRED" ||
        center.current_clusters) && (
        <section className="stack">
          <h4>{chrome.part3Stop2Title}</h4>
          <p className="hint">{chrome.part3NoNamesAtStop2Warning}</p>
          {active === "STOP2_CLUSTERS" ? (
            <form onSubmit={submitStop2}>
              <Stop2Table rows={stop2Rows} onChange={setStop2Rows} />
              <button type="submit">{chrome.submitPart3Stop2}</button>
            </form>
          ) : (
            <p className="hint">
              {chrome.stop2Completed}
              {center.current_clusters?.rows
                .map((r) => `${r.cluster}: ${r.decision}`)
                .join(", ")}
            </p>
          )}
        </section>
      )}

      {(active === "STOP3_NAMES" || center.current_names) && (
        <section className="stack">
          <h4>{chrome.part3Stop3Title}</h4>
          <p className="hint">{chrome.part3TargetGeneInNameWarning}</p>
          {active === "STOP3_NAMES" ? (
            <form onSubmit={submitStop3}>
              <Stop3Table rows={stop3Rows} onChange={setStop3Rows} />
              <button type="submit">{chrome.submitPart3Stop3}</button>
            </form>
          ) : (
            <p className="hint">
              {chrome.stop3Completed}
              {center.current_names?.rows
                .map((r) => `${r.cluster}: ${r.name}`)
                .join(", ")}
            </p>
          )}
        </section>
      )}

      {message && <p className="hint">{message}</p>}
    </div>
  );
}
