import { useState } from "react";

import type { StageWorkspaceView } from "../api/client";
import { chrome } from "../text/chrome";
import {
  extractLockedCellTypes,
  latestTaskStatus,
  taskStatusClass,
} from "./workspace_task_helpers";
import { BlockHead, CheckRow, FieldInput } from "./WorkspaceTaskParts";

export function WorkspacePostLock({
  ws,
  busy,
  onEnqueue,
}: {
  ws: StageWorkspaceView;
  busy: boolean;
  onEnqueue: (taskId: string, fields?: Record<string, unknown>) => void;
}) {
  const cellTypes = extractLockedCellTypes(ws);
  const isLocked =
    latestTaskStatus(ws, "formal_part1_lock") === "COMPLETED" ||
    Boolean(ws.results.evidence.lock);

  const [part2Group, setPart2Group] = useState("cell_type");
  const [lineage, setLineage] = useState("");
  const [barcodesPath, setBarcodesPath] = useState("");
  const [completedRounds, setCompletedRounds] = useState("0");
  const [stillMixed, setStillMixed] = useState(false);
  const [part4Group, setPart4Group] = useState("cell_type");
  const [lineageStopped, setLineageStopped] = useState(false);
  const [part5Arm, setPart5Arm] = useState("");
  const [part5Group, setPart5Group] = useState("cell_type");
  const [part5Model, setPart5Model] = useState("");
  const [singleSource, setSingleSource] = useState(false);
  const [blockFallback, setBlockFallback] = useState(false);

  const datalistId = `locked-types-${ws.id}`;
  const p2Status =
    latestTaskStatus(ws, "formal_part2_figures") ||
    latestTaskStatus(ws, "formal_part2_survey");
  const p3Status = latestTaskStatus(ws, "formal_part3_recluster");
  const p4Status =
    latestTaskStatus(ws, "formal_part4_figures") ||
    latestTaskStatus(ws, "formal_part4_survey");
  const p5Status = latestTaskStatus(ws, "formal_part5_prepare");
  const reportStatus = latestTaskStatus(ws, "formal_stage_report");

  return (
    <section className="card task-console-section">
      <div className="section-title-row">
        <div>
          <h4>{chrome.postLockTitle}</h4>
          <p className="hint">
            {isLocked ? chrome.postLockLockedNote : chrome.postLockPendingNote}
          </p>
        </div>
        <span className={taskStatusClass(isLocked ? "COMPLETED" : "")}>
          {isLocked ? "LOCKED" : chrome.notRunYet}
        </span>
      </div>

      <datalist id={datalistId}>
        {cellTypes.map((ct) => (
          <option key={ct} value={ct} />
        ))}
      </datalist>

      <div className="task-stage-grid">
        <div className="task-stage-block">
          <BlockHead title={chrome.part2TaskTitle} status={p2Status} />
          <FieldInput
            label={chrome.group}
            value={part2Group}
            onChange={setPart2Group}
          />
          <div className="task-action-row">
            <button
              type="button"
              disabled={busy || !part2Group.trim()}
              onClick={() =>
                onEnqueue("formal_part2_survey", { group: part2Group.trim() })
              }
            >
              {chrome.runPart2Survey}
            </button>
            <button
              type="button"
              disabled={busy || !part2Group.trim()}
              onClick={() =>
                onEnqueue("formal_part2_figures", { group: part2Group.trim() })
              }
            >
              {chrome.runPart2Figures}
            </button>
          </div>
        </div>

        <div className="task-stage-block">
          <BlockHead title={chrome.part3TaskTitle} status={p3Status} />
          <div className="task-inline-fields">
            <FieldInput
              label={chrome.lineageLabel}
              list={datalistId}
              value={lineage}
              placeholder={chrome.lineagePlaceholder}
              onChange={setLineage}
            />
            <label className="task-field">
              <span>{chrome.completedRounds}</span>
              <select
                value={completedRounds}
                onChange={(e) => setCompletedRounds(e.target.value)}
              >
                <option value="0">0</option>
                <option value="1">1</option>
                <option value="2">2</option>
              </select>
            </label>
          </div>
          <FieldInput
            label={chrome.barcodesOptional}
            value={barcodesPath}
            placeholder={chrome.barcodesPlaceholder}
            onChange={setBarcodesPath}
          />
          <CheckRow
            checked={stillMixed}
            label={chrome.stillMixed}
            onChange={setStillMixed}
          />
          <div className="task-action-row">
            <button
              type="button"
              disabled={busy || !lineage.trim()}
              onClick={() => {
                const payload: Record<string, unknown> = {
                  lineage: lineage.trim(),
                  completed_rounds: Number(completedRounds),
                  still_mixed: stillMixed,
                };
                if (barcodesPath.trim()) payload.barcodes = barcodesPath.trim();
                onEnqueue("formal_part3_recluster", payload);
              }}
            >
              {chrome.runPart3Recluster}
            </button>
          </div>
        </div>

        <div className="task-stage-block">
          <BlockHead title={chrome.part4TaskTitle} status={p4Status} />
          <FieldInput
            label={chrome.group}
            value={part4Group}
            onChange={setPart4Group}
          />
          <CheckRow
            checked={lineageStopped}
            label={chrome.lineageStoppedFlag}
            onChange={setLineageStopped}
          />
          <div className="task-action-row">
            <button
              type="button"
              disabled={busy || !part4Group.trim()}
              onClick={() =>
                onEnqueue("formal_part4_survey", {
                  group: part4Group.trim(),
                  lineage_stopped: lineageStopped,
                })
              }
            >
              {chrome.runPart4Survey}
            </button>
            <button
              type="button"
              disabled={busy || !part4Group.trim()}
              onClick={() =>
                onEnqueue("formal_part4_figures", {
                  group: part4Group.trim(),
                  lineage_stopped: lineageStopped,
                })
              }
            >
              {chrome.runPart4Figures}
            </button>
          </div>
        </div>

        <div className="task-stage-block">
          <BlockHead title={chrome.part5TaskTitle} status={p5Status} />
          <div className="task-inline-fields">
            <FieldInput
              label={chrome.armLabel}
              list={datalistId}
              value={part5Arm}
              placeholder={chrome.armPlaceholder}
              onChange={setPart5Arm}
            />
            <FieldInput
              label={chrome.group}
              value={part5Group}
              onChange={setPart5Group}
            />
          </div>
          <label className="task-field">
            <span>{chrome.modelLabel}</span>
            <select
              value={part5Model}
              onChange={(e) => setPart5Model(e.target.value)}
            >
              <option value="">{chrome.modelPrepareOnly}</option>
              <option value="limma_voom">limma_voom</option>
              <option value="edger_ql">edger_ql</option>
              <option value="deseq2">deseq2</option>
            </select>
          </label>
          <CheckRow
            checked={singleSource}
            label={chrome.singleSourceDeclared}
            onChange={setSingleSource}
          />
          <CheckRow
            checked={blockFallback}
            label={chrome.blockFallbackDeclared}
            onChange={setBlockFallback}
          />
          <div className="task-action-row">
            <button
              type="button"
              disabled={busy || !part5Arm.trim() || !part5Group.trim()}
              onClick={() => {
                const payload: Record<string, unknown> = {
                  arm: part5Arm.trim(),
                  group: part5Group.trim(),
                  single_source_declared: singleSource,
                  block_fallback_declared: blockFallback,
                };
                if (part5Model) payload.model = part5Model;
                onEnqueue("formal_part5_prepare", payload);
              }}
            >
              {chrome.runPart5Prepare}
            </button>
          </div>
        </div>
      </div>

      <div className="task-report-bar">
        <BlockHead title={chrome.stageReportTitle} status={reportStatus} />
        <button
          type="button"
          disabled={busy}
          onClick={() => onEnqueue("formal_stage_report", {})}
        >
          {chrome.runStageReport}
        </button>
      </div>
    </section>
  );
}
