import type { StageWorkspaceView } from "../api/client";

export function ResultsTab({ ws }: { ws: StageWorkspaceView }) {
  const sci = ws.results.scientific_status;
  return (
    <div className="stack" style={{ gap: "12px" }}>
      <div
        className="card"
        style={{ borderLeft: "4px solid var(--accent, #3b82f6)" }}
      >
        <h4>科学状态与推断上限</h4>
        <div
          className="row"
          style={{ gap: "8px", flexWrap: "wrap", margin: "8px 0" }}
        >
          <span className="badge">判决: {sci.scientific_status}</span>
          <span className="badge">校准: {sci.calibration_status}</span>
          <span className="badge">
            关联支持 (associated): {sci.associated ? "True" : "False"}
          </span>
          <span className="badge">
            Limma 主张: {sci.claims_limma ? "True" : "False"}
          </span>
        </div>
        <ul
          style={{
            margin: "4px 0 0 18px",
            fontSize: "12px",
            color: "var(--muted, #666)",
          }}
        >
          {sci.limits.map((lim, idx) => (
            <li key={idx}>{lim}</li>
          ))}
        </ul>
      </div>

      <div className="card">
        <h4>产物文件 ({ws.results.artifacts.length})</h4>
        {ws.results.artifacts.length === 0 ? (
          <p className="empty-state">尚未生成任何产物文件。</p>
        ) : (
          <table
            style={{
              width: "100%",
              fontSize: "12px",
              borderCollapse: "collapse",
            }}
          >
            <thead>
              <tr
                style={{
                  textAlign: "left",
                  borderBottom: "1px solid var(--border, #ddd)",
                }}
              >
                <th>相对路径</th>
                <th>状态</th>
                <th>SHA256</th>
              </tr>
            </thead>
            <tbody>
              {ws.results.artifacts.map((a) => (
                <tr
                  key={a.id}
                  style={{
                    borderBottom: "1px solid var(--border-light, #eee)",
                  }}
                >
                  <td style={{ padding: "4px 0" }}>
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
      </div>
    </div>
  );
}

export function ChecksTab({ ws }: { ws: StageWorkspaceView }) {
  return (
    <div className="stack" style={{ gap: "8px" }}>
      <h4>机器规则与审阅检查结果 ({ws.checks.length})</h4>
      {ws.checks.length === 0 ? (
        <p className="empty-state">尚未运行任何规则检查。</p>
      ) : (
        <table
          style={{
            width: "100%",
            fontSize: "12px",
            borderCollapse: "collapse",
          }}
        >
          <thead>
            <tr
              style={{
                textAlign: "left",
                borderBottom: "1px solid var(--border, #ddd)",
              }}
            >
              <th>规则</th>
              <th>判定</th>
              <th>详情</th>
              <th>时间</th>
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
                <tr
                  key={c.id}
                  style={{
                    borderBottom: "1px solid var(--border-light, #eee)",
                  }}
                >
                  <td style={{ padding: "6px 0", fontWeight: 600 }}>
                    {c.rule_id}
                  </td>
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
                  <td style={{ color: "var(--muted, #888)", fontSize: "11px" }}>
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
    <div className="stack" style={{ gap: "8px" }}>
      <h4>任务执行日志 ({ws.logs.length})</h4>
      {ws.logs.length === 0 ? (
        <p className="empty-state">尚无任务执行记录。</p>
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
              <p style={{ color: "var(--danger, #dc2626)", margin: "4px 0 0" }}>
                失败原因: {l.failure_reason}
              </p>
            ) : null}
            <small style={{ color: "var(--muted, #888)" }}>
              创建时间:{" "}
              {l.created_at ? new Date(l.created_at).toLocaleString() : "-"}
            </small>
          </div>
        ))
      )}
    </div>
  );
}
