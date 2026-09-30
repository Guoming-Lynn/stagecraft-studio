import {
  cancelRun,
  errorText,
  loadSteps,
  type Bootstrap,
  type RunListItem,
  type RunView,
  type StepView,
} from "../api/client";
import { chrome } from "../text/chrome";

type Mode = "quicklook" | "formal" | "environment";

export function TopBar({
  bootstrap,
  runs,
  run,
  mode,
  onMode,
  onRun,
  onSteps,
  onError,
}: {
  bootstrap: Bootstrap | null;
  runs: RunListItem[];
  run: RunView | null;
  mode: Mode;
  onMode: (mode: Mode) => void;
  onRun: (run: RunView) => void;
  onSteps: (steps: StepView[]) => void;
  onError: (message: string) => void;
}) {
  return (
    <header className="topbar">
      <div className="brand">
        <svg
          className="brand-icon"
          viewBox="0 0 24 24"
          fill="none"
          stroke="currentColor"
          strokeWidth="2"
        >
          <circle cx="12" cy="12" r="3" />
          <path d="M19.07 4.93a10 10 0 0 1 0 14.14M4.93 4.93a10 10 0 0 0 0 14.14" />
        </svg>
        <span>Stagecraft</span>
        <span className="brand-badge">STUDIO</span>
      </div>
      <label>
        {chrome.project}
        <select
          value={run?.run_id ?? ""}
          onChange={(event) => {
            window.location.hash = event.target.value
              ? `#/runs/${event.target.value}`
              : "";
          }}
        >
          <option value="">{chrome.newRun}</option>
          {runs.map((item) => (
            <option key={item.run_id} value={item.run_id}>
              {item.run_id} · {item.status_label}
            </option>
          ))}
        </select>
      </label>
      <div className="topbar-nav">
        <button
          type="button"
          className={mode === "quicklook" ? "on" : ""}
          onClick={() => onMode("quicklook")}
        >
          {chrome.quicklook}
        </button>
        <button
          type="button"
          className={mode === "formal" ? "on" : ""}
          onClick={() => onMode("formal")}
        >
          {chrome.formal}
        </button>
        <button
          type="button"
          className={mode === "environment" ? "on" : ""}
          onClick={() => onMode("environment")}
        >
          {bootstrap?.environment_ok
            ? chrome.environmentOk
            : chrome.environmentBad}
        </button>
        <button
          type="button"
          disabled={!run?.can_cancel}
          onClick={() => {
            if (!run) return;
            void cancelRun(run.run_id)
              .then((next) => {
                onRun(next);
                return loadSteps(next.run_id).then(onSteps);
              })
              .catch((reason: unknown) => onError(errorText(reason)));
          }}
        >
          {chrome.cancel}
        </button>
      </div>
    </header>
  );
}
