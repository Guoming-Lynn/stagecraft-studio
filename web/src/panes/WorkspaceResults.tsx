import type { StageWorkspaceView } from "../api/client";
import {
  chrome,
  scientificLimitText,
  scientificStatusNote,
  scientificStatusTitle,
} from "../text/chrome";

export function ResultsTab({ ws }: { ws: StageWorkspaceView }) {
  const sci = ws.results.scientific_status;
  return (
    <div className="stack workspace-section">
      <section className="card card-scientific scientific-status-card">
        <div className="scientific-status-heading">
          <div className="scientific-status-copy">
            <h4>{scientificStatusTitle(sci.scientific_status)}</h4>
            <p>{scientificStatusNote(sci.scientific_status)}</p>
          </div>
          <span className="status-code" title={chrome.scientificStatusCode}>
            {sci.scientific_status}
          </span>
        </div>
        <dl className="scientific-status-facts">
          <div>
            <dt>{chrome.calibration}</dt>
            <dd>{chrome.calibrationReadable}</dd>
          </div>
          <div>
            <dt>{chrome.association}</dt>
            <dd>{sci.associated ? chrome.supported : chrome.notSupported}</dd>
          </div>
          <div>
            <dt>{chrome.limmaClaim}</dt>
            <dd>{sci.claims_limma ? chrome.reported : chrome.notReported}</dd>
          </div>
        </dl>
        <h5 className="interpretation-heading">{chrome.scientificLimits}</h5>
        <ul className="limit-list">
          {sci.limits
            .filter((lim) => scientificLimitText(lim))
            .map((lim) => (
              <li key={lim}>{scientificLimitText(lim)}</li>
            ))}
        </ul>
      </section>

      <section className="card artifact-card">
        <h4>
          {chrome.artifactFiles} ({ws.results.artifacts.length})
        </h4>
        {ws.results.artifacts.length === 0 ? (
          <p className="empty-state">{chrome.noArtifacts}</p>
        ) : (
          <table className="artifact-table">
            <thead>
              <tr>
                <th>{chrome.relativePath}</th>
                <th>{chrome.status}</th>
                <th>SHA-256</th>
              </tr>
            </thead>
            <tbody>
              {ws.results.artifacts.map((a) => (
                <tr key={a.id}>
                  <td>
                    <code>{a.relative_path}</code>
                  </td>
                  <td>{a.artifact_status}</td>
                  <td>
                    <code>{a.content_hash.slice(0, 12)}...</code>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </section>
    </div>
  );
}

export function ChecksTab({ ws }: { ws: StageWorkspaceView }) {
  return (
    <div className="stack workspace-section">
      <h4>
        {chrome.ruleChecks} ({ws.checks.length})
      </h4>
      {ws.checks.length === 0 ? (
        <p className="empty-state">{chrome.noChecks}</p>
      ) : (
        <table className="checks-table">
          <thead>
            <tr>
              <th>{chrome.rule}</th>
              <th>{chrome.decision}</th>
              <th>{chrome.details}</th>
              <th>{chrome.time}</th>
            </tr>
          </thead>
          <tbody>
            {ws.checks.map((c) => {
              const color =
                c.rule_status === "PASS"
                  ? "var(--success, #16a34a)"
                  : c.rule_status === "WARN"
                    ? "var(--warning, #ca8a04)"
                    : "var(--danger, #dc2626)";
              return (
                <tr key={c.id}>
                  <td className="rule-id">{c.rule_id}</td>
                  <td>
                    <span style={{ color, fontWeight: 700 }}>
                      {c.rule_status}
                    </span>
                  </td>
                  <td>
                    <pre style={{ margin: 0, fontSize: "11px" }}>
                      {JSON.stringify(c.detail, null, 1)}
                    </pre>
                  </td>
                  <td className="check-time">
                    {c.checked_at
                      ? new Date(c.checked_at).toLocaleTimeString()
                      : "-"}
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      )}
    </div>
  );
}

export function LogsTab({ ws }: { ws: StageWorkspaceView }) {
  return (
    <div className="stack workspace-section">
      <h4>
        {chrome.taskLogs} ({ws.logs.length})
      </h4>
      {ws.logs.length === 0 ? (
        <p className="empty-state">{chrome.noTaskLogs}</p>
      ) : (
        ws.logs.map((l) => (
          <div key={l.id} className="card" style={{ fontSize: "13px" }}>
            <div className="row spread">
              <strong>
                #{l.id} {l.task_id}
              </strong>
              <span className="badge">{l.job_status}</span>
            </div>
            {l.failure_reason ? (
              <p style={{ color: "var(--rose-primary)", margin: "4px 0 0" }}>
                {chrome.failureReason}: {l.failure_reason}
              </p>
            ) : null}
            <small style={{ color: "var(--text-muted)" }}>
              {chrome.createdAt}:{" "}
              {l.created_at ? new Date(l.created_at).toLocaleString() : "-"}
            </small>
          </div>
        ))
      )}
    </div>
  );
}
