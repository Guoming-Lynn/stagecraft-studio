import { useState } from "react";

import { chrome } from "../text/chrome";
import { Gallery } from "./Gallery";
import { ProtocolForm } from "./ProtocolForm";
import { ReviewCenter } from "./ReviewCenter";
import { StageWorkspace } from "./StageWorkspace";

export function FormalDesk() {
  const [pane, setPane] = useState<
    "workspace" | "gallery" | "review" | "design"
  >("workspace");
  return (
    <div className="stack">
      <div className="tabs">
        <button
          type="button"
          className={pane === "workspace" ? "on" : ""}
          onClick={() => setPane("workspace")}
        >
          {chrome.workspace}
        </button>
        <button
          type="button"
          className={pane === "gallery" ? "on" : ""}
          onClick={() => setPane("gallery")}
        >
          {chrome.gallery}
        </button>
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
      {pane === "workspace" && <StageWorkspace />}
      {pane === "gallery" && <Gallery />}
      {pane === "review" && <ReviewCenter />}
      {pane === "design" && <ProtocolForm />}
    </div>
  );
}
