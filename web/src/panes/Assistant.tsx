import { chrome } from "../text/chrome";

export function Assistant() {
  return (
    <div className="assistant-card">
      <p className="hint">{chrome.assistantNote}</p>
    </div>
  );
}
