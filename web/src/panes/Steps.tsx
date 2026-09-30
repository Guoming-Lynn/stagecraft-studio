import type { StepView } from "../api/client";
import { chrome } from "../text/chrome";

export function Steps({
  steps,
  selected,
  onSelect,
}: {
  steps: StepView[];
  selected: string;
  onSelect: (stepId: string) => void;
}) {
  if (steps.length === 0) return <p className="hint">{chrome.noRun}</p>;
  return (
    <ol className="timeline">
      {steps.map((step) => (
        <li key={step.step_id}>
          <button
            type="button"
            className={step.step_id === selected ? "step selected" : "step"}
            onClick={() => onSelect(step.step_id)}
          >
            <span>{step.name}</span>
            <span className={`mark mark-${step.status}`}>
              {step.status_label}
            </span>
          </button>
        </li>
      ))}
    </ol>
  );
}
