import { useState } from "react";

import {
  cancelFormalJob,
  enqueueStageTask,
  errorText,
  type StageWorkspaceView,
} from "../api/client";
import { chrome } from "../text/chrome";
import {
  extractProtocolLibraries,
  latestTaskStatus,
} from "./workspace_task_helpers";
import { WorkspacePostLock } from "./WorkspacePostLock";
import { ActionCell, ActiveJobsBanner } from "./WorkspaceTaskParts";

export function WorkspaceTasks({
  ws,
  onRefresh,
  onMessage,
}: {
  ws: StageWorkspaceView;
  onRefresh: () => void;
  onMessage: (text: string) => void;
}) {
  const [busy, setBusy] = useState(false);
  const [inputOverrides, setInputOverrides] = useState<Record<string, string>>(
    {},
  );
  const [formatOverrides, setFormatOverrides] = useState<
    Record<string, string>
  >({});

  const libraries = extractProtocolLibraries(ws);
  const activeJobs = ws.parameters.filter(
    (job) => job.job_status === "QUEUED" || job.job_status === "RUNNING",
  );
  const mergeStatus = latestTaskStatus(ws, "formal_part1_merge");
  const gridStatus = latestTaskStatus(ws, "formal_part1_grid");

  const runTask = (taskId: string, fields: Record<string, unknown> = {}) => {
    setBusy(true);
    onMessage("");
    void enqueueStageTask(ws.id, taskId, fields)
      .then((res) => {
        onMessage(`${chrome.taskQueuedNotice}: #${res.id} (${res.task_id})`);
        onRefresh();
      })
      .catch((err: unknown) => onMessage(errorText(err)))
      .finally(() => setBusy(false));
  };

  const buildLoadFields = (libId: string): Record<string, unknown> => {
    const fields: Record<string, unknown> = { library_id: libId };
    const customInput = (inputOverrides[libId] ?? "").trim();
    const customFormat = (formatOverrides[libId] ?? "").trim();
    if (customInput) fields.input = customInput;
    if (customFormat) fields.format = customFormat;
    return fields;
  };

  const buildQcFields = (libId: string): Record<string, unknown> => {
    const fields: Record<string, unknown> = { library_id: libId };
    const customInput = (inputOverrides[libId] ?? "").trim();
    if (customInput) fields.source = customInput;
    return fields;
  };

  const runBatch = (
    taskId: "formal_part1_load" | "formal_part1_qc",
    makeFields: (libId: string) => Record<string, unknown>,
  ) => {
    setBusy(true);
    onMessage("");
    void libraries
      .reduce<Promise<unknown>>(
        (chain, lib) =>
          chain.then(() =>
            enqueueStageTask(ws.id, taskId, makeFields(lib.library_id)),
          ),
        Promise.resolve(),
      )
      .then(() => {
        onMessage(`${chrome.taskQueuedNotice}: ${taskId}`);
        onRefresh();
      })
      .catch((err: unknown) => onMessage(errorText(err)))
      .finally(() => setBusy(false));
  };

  return (
    <div className="stack workspace-section">
      <ActiveJobsBanner
        jobs={activeJobs}
        busy={busy}
        onCancel={(jobId) => {
          setBusy(true);
          void cancelFormalJob(jobId)
            .then(() => onRefresh())
            .catch((err: unknown) => onMessage(errorText(err)))
            .finally(() => setBusy(false));
        }}
      />

      <section className="card task-console-section">
        <div className="section-title-row">
          <div>
            <h4>{chrome.part1PipelineTitle}</h4>
            <p className="hint">{chrome.part1PipelineNote}</p>
          </div>
          {libraries.length > 1 ? (
            <div className="task-action-row">
              <button
                type="button"
                disabled={busy || ws.invalidated}
                onClick={() => runBatch("formal_part1_load", buildLoadFields)}
              >
                {chrome.runAllLoad}
              </button>
              <button
                type="button"
                disabled={busy || ws.invalidated}
                onClick={() => runBatch("formal_part1_qc", buildQcFields)}
              >
                {chrome.runAllQc}
              </button>
            </div>
          ) : null}
        </div>

        <div className="table-scroll">
          <table className="task-library-table">
            <thead>
              <tr>
                <th>{chrome.library}</th>
                <th>{chrome.libraryInputOverride}</th>
                <th>{chrome.inputFormat}</th>
                <th>{chrome.runLoad}</th>
                <th>{chrome.runQc}</th>
              </tr>
            </thead>
            <tbody>
              {libraries.map((lib) => {
                const loadStat = latestTaskStatus(
                  ws,
                  "formal_part1_load",
                  lib.library_id,
                );
                const qcStat = latestTaskStatus(
                  ws,
                  "formal_part1_qc",
                  lib.library_id,
                );
                return (
                  <tr key={lib.library_id}>
                    <td>
                      <strong>{lib.library_id}</strong>
                      <div className="hint">
                        {lib.dataset}
                        {lib.donor_id ? ` · ${lib.donor_id}` : ""}
                        {lib.source_block ? ` · ${lib.source_block}` : ""}
                      </div>
                    </td>
                    <td>
                      <input
                        value={inputOverrides[lib.library_id] ?? ""}
                        placeholder={ws.inputs.data_path}
                        aria-label={`${lib.library_id} ${chrome.inputPath}`}
                        onChange={(e) =>
                          setInputOverrides((prev) => ({
                            ...prev,
                            [lib.library_id]: e.target.value,
                          }))
                        }
                      />
                    </td>
                    <td>
                      <select
                        value={formatOverrides[lib.library_id] ?? ""}
                        aria-label={`${lib.library_id} ${chrome.inputFormat}`}
                        onChange={(e) =>
                          setFormatOverrides((prev) => ({
                            ...prev,
                            [lib.library_id]: e.target.value,
                          }))
                        }
                      >
                        <option value="">{chrome.formatAuto}</option>
                        <option value="h5ad">h5ad</option>
                        <option value="10x_h5">10x_h5</option>
                        <option value="10x_mtx">10x_mtx</option>
                      </select>
                    </td>
                    <td>
                      <ActionCell
                        status={loadStat}
                        label={chrome.runLoad}
                        disabled={busy || ws.invalidated}
                        onClick={() =>
                          runTask(
                            "formal_part1_load",
                            buildLoadFields(lib.library_id),
                          )
                        }
                      />
                    </td>
                    <td>
                      <ActionCell
                        status={qcStat}
                        label={chrome.runQc}
                        disabled={busy || ws.invalidated}
                        onClick={() =>
                          runTask(
                            "formal_part1_qc",
                            buildQcFields(lib.library_id),
                          )
                        }
                      />
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>

        <div className="task-pipeline-bar">
          <ActionCell
            status={mergeStatus}
            label={chrome.runMerge}
            disabled={busy || ws.invalidated}
            onClick={() => runTask("formal_part1_merge", {})}
          />
          <ActionCell
            status={gridStatus}
            label={chrome.runGrid}
            disabled={busy || ws.invalidated}
            onClick={() => runTask("formal_part1_grid", {})}
          />
          {gridStatus === "COMPLETED" ? (
            <button
              type="button"
              className="primary-action"
              onClick={() =>
                window.dispatchEvent(
                  new CustomEvent("stagecraft:formal-navigate", {
                    detail: { pane: "review", runId: ws.id },
                  }),
                )
              }
            >
              {chrome.openReviewPane}
            </button>
          ) : null}
        </div>
      </section>

      <WorkspacePostLock
        ws={ws}
        busy={busy || ws.invalidated}
        onEnqueue={runTask}
      />
    </div>
  );
}
