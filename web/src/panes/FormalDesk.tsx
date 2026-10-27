import { useEffect, useState } from "react";

import { hasProposal } from "../proposal_store";
import { chrome } from "../text/chrome";
import { Gallery } from "./Gallery";
import { ProtocolForm } from "./ProtocolForm";
import { ReviewCenter } from "./ReviewCenter";
import { StageWorkspace } from "./StageWorkspace";

export function FormalDesk() {
  const [pane, setPane] = useState<
    "workspace" | "gallery" | "review" | "design"
  >(() => (hasProposal() ? "design" : "workspace"));
  useEffect(() => {
    const apply = () => setPane("design");
    window.addEventListener("stagecraft:apply-proposal", apply);
    return () => window.removeEventListener("stagecraft:apply-proposal", apply);
  }, []);
  return (
    <div className="formal-desk stack">
      <header className="formal-header">
        <div>
          <h1>{chrome.formal}</h1>
        </div>
        <span className="formal-scope">Part 1–5</span>
      </header>
      <nav className="tabs formal-nav" aria-label={chrome.formal}>
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
      </nav>
      {pane === "workspace" && <StageWorkspace />}
      {pane === "gallery" && <Gallery />}
      {pane === "review" && <ReviewCenter />}
      {pane === "design" && <ProtocolForm />}
    </div>
  );
}
