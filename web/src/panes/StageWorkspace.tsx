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
    <div className="stack">
      {message ? <p className="log-error">{message}</p> : null}
      <div
        className="row spread"
        style={{ alignItems: "center", marginBottom: "8px" }}
      >
        <div className="row" style={{ alignItems: "center", gap: "8px" }}>
          <label htmlFor="stage-run-select">
            <strong>Stage Run:</strong>
          </label>
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
        </div>
        {ws ? (
          <span className="badge" style={{ fontSize: "12px" }}>
            状态: {ws.stage_status} {ws.invalidated ? "(已失效)" : ""}
          </span>
        ) : null}
      </div>

      <div className="tabs">
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
      </div>

      {ws ? (
        <div
          className="pane-content"
          style={{ padding: "12px", overflowY: "auto" }}
        >
          {tab === "inputs" && <InputsTab ws={ws} />}
          {tab === "parameters" && <ParametersTab ws={ws} />}
          {tab === "results" && <ResultsTab ws={ws} />}
          {tab === "checks" && <ChecksTab ws={ws} />}
          {tab === "logs" && <LogsTab ws={ws} />}
        </div>
      ) : (
        <p>正在加载工作区数据...</p>
      )}
    </div>
  );
}

function InputsTab({ ws }: { ws: StageWorkspaceView }) {
  const { inputs } = ws;
  return (
    <div className="stack" style={{ gap: "12px" }}>
      <div className="card">
        <h4>基本信息</h4>
        <p>
          <strong>目标基因:</strong> {inputs.target_gene || "未设定"} |{" "}
          <strong>物种:</strong> {inputs.species || "未设定"}
        </p>
        <p>
          <strong>数据文件:</strong> <code>{inputs.data_path}</code>
        </p>
        <p>
          <strong>项目路径:</strong> <code>{inputs.root_path}</code>
        </p>
      </div>
      <div className="card">
        <h4>协议防篡改哈希</h4>
        <p>
          <strong>协议 SHA256:</strong>{" "}
          <code>{inputs.protocol_hash || "无"}</code>
        </p>
        <p>
          <strong>输入数据 SHA256:</strong>{" "}
          <code>{inputs.input_hash || "无"}</code>
        </p>
      </div>
    </div>
  );
}

function ParametersTab({ ws }: { ws: StageWorkspaceView }) {
  return (
    <div className="stack" style={{ gap: "8px" }}>
      {ws.parameters.length === 0 ? (
        <p className="empty-state">尚未入队任何分析任务。</p>
      ) : (
        ws.parameters.map((p) => (
          <div key={p.job_id} className="card" style={{ fontSize: "13px" }}>
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
                background: "var(--bg-card)",
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
