import { useEffect, useState } from "react";

import { hasProposal } from "../proposal_store";
import { chrome } from "../text/chrome";
import { Gallery } from "./Gallery";
import { ProtocolForm } from "./ProtocolForm";
import { ReviewCenter } from "./ReviewCenter";
import { StageWorkspace, type WorkspaceTab } from "./StageWorkspace";

type FormalPane = "workspace" | "gallery" | "review" | "design";

type NavigateDetail = {
  pane?: FormalPane;
  runId?: number;
  tab?: WorkspaceTab;
};

export function FormalDesk() {
  const [pane, setPane] = useState<FormalPane>(() =>
    hasProposal() ? "design" : "workspace",
  );
  const [targetRunId, setTargetRunId] = useState<number | null>(null);
  const [workspaceTab, setWorkspaceTab] = useState<WorkspaceTab>("results");

  useEffect(() => {
    const apply = () => setPane("design");
    const navigate = (event: Event) => {
      const detail = (event as CustomEvent<NavigateDetail>).detail;
      if (!detail) return;
      if (typeof detail.runId === "number") setTargetRunId(detail.runId);
      if (detail.tab) setWorkspaceTab(detail.tab);
      if (detail.pane) setPane(detail.pane);
    };
    window.addEventListener("stagecraft:apply-proposal", apply);
    window.addEventListener("stagecraft:formal-navigate", navigate);
    return () => {
      window.removeEventListener("stagecraft:apply-proposal", apply);
      window.removeEventListener("stagecraft:formal-navigate", navigate);
    };
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
      {pane === "workspace" && (
        <StageWorkspace initialRunId={targetRunId} initialTab={workspaceTab} />
      )}
      {pane === "gallery" && <Gallery />}
      {pane === "review" && <ReviewCenter initialRunId={targetRunId} />}
      {pane === "design" && <ProtocolForm />}
    </div>
  );
}
