import { useEffect, useState } from "react";

import {
  errorText,
  loadStageRuns,
  loadStageWorkspace,
  type StageRunItem,
  type StageWorkspaceView,
} from "../api/client";
import { chrome } from "../text/chrome";
import { ChecksTab, LogsTab, ResultsTab } from "./WorkspaceResults";

type Tab = "inputs" | "parameters" | "results" | "checks" | "logs";

export function StageWorkspace() {
  const [runs, setRuns] = useState<StageRunItem[]>([]);
  const [runId, setRunId] = useState<number | null>(null);
  const [ws, setWs] = useState<StageWorkspaceView | null>(null);
  const [tab, setTab] = useState<Tab>("results");
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
      setWs(null);
      return;
    }
    void loadStageWorkspace(runId)
      .then(setWs)
      .catch((err: unknown) => setMessage(errorText(err)));
  }, [runId]);

  if (runs.length === 0) {
    return (
      <div className="empty-state">
        <p>{chrome.formalNote}</p>
      </div>
    );
  }

  return (
    <div className="stage-workspace stack">
      {message ? <p className="log-error">{message}</p> : null}
      <div className="workspace-toolbar">
        <label className="run-selector" htmlFor="stage-run-select">
          <span>{chrome.project}</span>
          <select
            id="stage-run-select"
            value={runId ?? ""}
            onChange={(e) => setRunId(Number(e.target.value))}
          >
            {runs.map((r) => (
              <option key={r.id} value={r.id}>
                Run #{r.id} ({r.stage_status})
              </option>
            ))}
          </select>
        </label>
        {ws ? (
          <span className="workspace-status badge">
            {chrome.workspaceStatus}: {ws.stage_status}{" "}
            {ws.invalidated ? "(INVALIDATED)" : ""}
          </span>
        ) : null}
      </div>

      <nav className="tabs workspace-tabs" aria-label={chrome.workspace}>
        <button
          type="button"
          className={tab === "inputs" ? "on" : ""}
          onClick={() => setTab("inputs")}
        >
          {chrome.input}
        </button>
        <button
          type="button"
          className={tab === "parameters" ? "on" : ""}
          onClick={() => setTab("parameters")}
        >
          {chrome.parameters}
        </button>
        <button
          type="button"
          className={tab === "results" ? "on" : ""}
          onClick={() => setTab("results")}
        >
          {chrome.results}
        </button>
        <button
          type="button"
          className={tab === "checks" ? "on" : ""}
          onClick={() => setTab("checks")}
        >
          {chrome.checks}
        </button>
        <button
          type="button"
          className={tab === "logs" ? "on" : ""}
          onClick={() => setTab("logs")}
        >
          {chrome.log}
        </button>
      </nav>

      {ws ? (
        <div className="pane-content formal-content">
          {tab === "inputs" && <InputsTab ws={ws} />}
          {tab === "parameters" && <ParametersTab ws={ws} />}
          {tab === "results" && <ResultsTab ws={ws} />}
          {tab === "checks" && <ChecksTab ws={ws} />}
          {tab === "logs" && <LogsTab ws={ws} />}
        </div>
      ) : (
        <p>{chrome.workspaceLoading}</p>
      )}
    </div>
  );
}

function InputsTab({ ws }: { ws: StageWorkspaceView }) {
  const { inputs } = ws;
  return (
    <div className="stack workspace-section">
      <section className="card input-summary">
        <h4>{chrome.inputSummary}</h4>
        <dl className="key-value-grid">
          <div>
            <dt>{chrome.gene}</dt>
            <dd>{inputs.target_gene || "-"}</dd>
          </div>
          <div>
            <dt>{chrome.species}</dt>
            <dd>{inputs.species || "-"}</dd>
          </div>
          <div className="wide">
            <dt>{chrome.dataFile}</dt>
            <dd>
              <code>{inputs.data_path}</code>
            </dd>
          </div>
          <div className="wide">
            <dt>{chrome.projectPath}</dt>
            <dd>
              <code>{inputs.root_path}</code>
            </dd>
          </div>
        </dl>
      </section>
      <section className="card">
        <h4>{chrome.protocolHash}</h4>
        <dl className="key-value-grid hash-grid">
          <div className="wide">
            <dt>{chrome.protocolHash}</dt>
            <dd>
              <code>{inputs.protocol_hash || "无"}</code>
            </dd>
          </div>
          <div className="wide">
            <dt>{chrome.inputHash}</dt>
            <dd>
              <code>{inputs.input_hash || "无"}</code>
            </dd>
          </div>
        </dl>
      </section>
    </div>
  );
}

function ParametersTab({ ws }: { ws: StageWorkspaceView }) {
  return (
    <div className="stack workspace-section">
      {ws.parameters.length === 0 ? (
        <p className="empty-state">{chrome.noQueuedTasks}</p>
      ) : (
        ws.parameters.map((p) => (
          <div key={p.job_id} className="card parameter-card">
            <div className="row spread">
              <strong>
                Job #{p.job_id}: {p.task_id}
              </strong>
              <span className="badge">{p.job_status}</span>
            </div>
            <pre
              style={{
                margin: "6px 0 0",
                padding: "6px",
                background: "var(--bg-code)",
              }}
            >
              {JSON.stringify(p.fields, null, 2)}
            </pre>
          </div>
        ))
      )}
    </div>
  );
}
