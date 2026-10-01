import { useState } from "react";

import { chrome } from "../text/chrome";
import { ProtocolForm } from "./ProtocolForm";
import { ReviewCenter } from "./ReviewCenter";

export function FormalDesk() {
  const [pane, setPane] = useState<"review" | "design">("review");
  return (
    <div className="stack">
      <div className="tabs">
        <button
          type="button"
          className={pane === "review" ? "on" : ""}
          onClick={() => setPane("review")}
        >
          {chrome.review}
        </button>
        <button
          type="button"
          className={pane === "design" ? "on" : ""}
          onClick={() => setPane("design")}
        >
          {chrome.design}
        </button>
      </div>
      {pane === "review" ? <ReviewCenter /> : <ProtocolForm />}
    </div>
  );
}
