import type { StageWorkspaceView } from "../api/client";
import { chrome } from "../text/chrome";
import { taskStatusClass } from "./workspace_task_helpers";

export function ActionCell({
  status,
  label,
  disabled,
  onClick,
}: {
  status: string;
  label: string;
  disabled: boolean;
  onClick: () => void;
}) {
  return (
    <div className="task-cell-actions">
      <span className={taskStatusClass(status)}>
        {status || chrome.notRunYet}
      </span>
      <button type="button" disabled={disabled} onClick={onClick}>
        {label}
      </button>
    </div>
  );
}

export function BlockHead({
  title,
  status,
}: {
  title: string;
  status: string;
}) {
  return (
    <div className="row spread">
      <strong>{title}</strong>
      <span className={taskStatusClass(status)}>
        {status || chrome.notRunYet}
      </span>
    </div>
  );
}

export function FieldInput({
  label,
  value,
  list,
  placeholder,
  onChange,
}: {
  label: string;
  value: string;
  list?: string;
  placeholder?: string;
  onChange: (next: string) => void;
}) {
  return (
    <label className="task-field">
      <span>{label}</span>
      <input
        list={list}
        value={value}
        placeholder={placeholder}
        onChange={(e) => onChange(e.target.value)}
      />
    </label>
  );
}

export function CheckRow({
  checked,
  label,
  onChange,
}: {
  checked: boolean;
  label: string;
  onChange: (next: boolean) => void;
}) {
  return (
    <label className="task-check">
      <input
        type="checkbox"
        checked={checked}
        onChange={(e) => onChange(e.target.checked)}
      />
      <span>{label}</span>
    </label>
  );
}

export function ActiveJobsBanner({
  jobs,
  busy,
  onCancel,
}: {
  jobs: StageWorkspaceView["parameters"];
  busy: boolean;
  onCancel: (jobId: number) => void;
}) {
  if (jobs.length === 0) return null;
  return (
    <section className="card task-active-queue">
      <h4>{chrome.activeJobsTitle}</h4>
      <div className="stack">
        {jobs.map((job) => (
          <div key={job.job_id} className="row spread task-active-item">
            <div className="row">
              <strong>
                Job #{job.job_id} · {job.task_id}
              </strong>
              {job.fields.library_id ? (
                <code>{String(job.fields.library_id)}</code>
              ) : null}
              <span className={taskStatusClass(job.job_status)}>
                {job.job_status}
              </span>
            </div>
            <button
              type="button"
              disabled={busy}
              onClick={() => onCancel(job.job_id)}
            >
              {chrome.cancelJob}
            </button>
          </div>
        ))}
      </div>
    </section>
  );
}
