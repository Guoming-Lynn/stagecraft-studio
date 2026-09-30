import { useEffect, useState } from "react";
import { Group, Panel, Separator } from "react-resizable-panels";

import {
  errorText,
  loadBootstrap,
  loadRun,
  loadRuns,
  loadSource,
  loadSteps,
  loadTree,
  rememberToken,
  revealRun,
  startDemo,
  type Bootstrap,
  type RunListItem,
  type RunView,
  type SourceView,
  type StepView,
  type TreeEntry,
} from "./api/client";
import { readLayout, saveLayout } from "./layout_store";
import { Assistant } from "./panes/Assistant";
import { Environment } from "./panes/Environment";
import { Files } from "./panes/Files";
import { FileView } from "./panes/FileView";
import { Images } from "./panes/Images";
import { StartForm } from "./panes/StartForm";
import { StepDetail } from "./panes/StepDetail";
import { Steps } from "./panes/Steps";
import { TopBar } from "./panes/TopBar";
import { chrome } from "./text/chrome";

export function App() {
  const [bootstrap, setBootstrap] = useState<Bootstrap | null>(null);
  const [runs, setRuns] = useState<RunListItem[]>([]);
  const [run, setRun] = useState<RunView | null>(null);
  const [steps, setSteps] = useState<StepView[]>([]);
  const [tree, setTree] = useState<TreeEntry[]>([]);
  const [source, setSource] = useState<SourceView | null>(null);
  const [stepId, setStepId] = useState("");
  const [left, setLeft] = useState<"steps" | "files">("steps");
  const [right, setRight] = useState<"images" | "assistant">("images");
  const [mode, setMode] = useState<"quicklook" | "formal" | "environment">(
    "quicklook",
  );
  const [focus, setFocus] = useState("");
  const [fileRel, setFileRel] = useState("");
  const [error, setError] = useState("");
  const [layout] = useState(readLayout);

  useEffect(() => {
    void loadBootstrap()
      .then((next) => {
        rememberToken(next.token);
        setBootstrap(next);
      })
      .catch((reason: unknown) => setError(errorText(reason)));
  }, []);

  useEffect(() => {
    if (!bootstrap) return;
    let timer = 0;
    let stop = false;
    const tick = () => {
      window.clearTimeout(timer);
      const runId = runIdFromHash();
      void loadRuns()
        .then((list) => {
          if (!stop) setRuns(list);
        })
        .catch((reason: unknown) => setError(errorText(reason)));
      if (!runId) {
        setRun(null);
        setSteps([]);
        setTree([]);
        return;
      }
      void Promise.all([loadRun(runId), loadSteps(runId), loadTree(runId)])
        .then(([nextRun, nextSteps, nextTree]) => {
          if (stop) return;
          setRun(nextRun);
          setSteps(nextSteps);
          setTree(nextTree);
          if (nextRun.status === "running" || nextRun.status === "starting") {
            timer = window.setTimeout(tick, 3000);
          }
        })
        .catch((reason: unknown) => setError(errorText(reason)));
    };
    tick();
    window.addEventListener("hashchange", tick);
    return () => {
      stop = true;
      window.clearTimeout(timer);
      window.removeEventListener("hashchange", tick);
    };
  }, [bootstrap]);

  useEffect(() => {
    if (!stepId && steps.length > 0) {
      const running = steps.find((item) => item.status === "running");
      setStepId((running ?? steps[0]).step_id);
    }
  }, [stepId, steps]);

  useEffect(() => {
    if (!stepId) return;
    void loadSource(stepId)
      .then(setSource)
      .catch(() => setSource(null));
  }, [stepId]);

  const step = steps.find((item) => item.step_id === stepId) ?? null;
  const selected = step?.step_id === source?.step_id ? source : null;

  return (
    <div className="app">
      <TopBar
        bootstrap={bootstrap}
        runs={runs}
        run={run}
        mode={mode}
        onMode={setMode}
        onRun={setRun}
        onSteps={setSteps}
        onError={setError}
      />
      {error ? <p className="log-error">{error}</p> : null}
      <Group
        orientation="horizontal"
        defaultLayout={layout}
        onLayoutChanged={(next, meta) => {
          if (meta.isUserInteraction) saveLayout(next);
        }}
      >
        <Panel id="left" defaultSize="22%" minSize="16%">
          <div className="pane">
            <div className="tabs">
              <button
                type="button"
                className={left === "steps" ? "on" : ""}
                onClick={() => setLeft("steps")}
              >
                {chrome.steps}
              </button>
              <button
                type="button"
                className={left === "files" ? "on" : ""}
                onClick={() => setLeft("files")}
              >
                {chrome.files}
              </button>
            </div>
            {left === "steps" ? (
              <Steps steps={steps} selected={stepId} onSelect={setStepId} />
            ) : null}
            {left === "files" ? (
              <Files
                entries={tree}
                onReveal={() => {
                  if (run) void revealRun(run.run_id);
                }}
                onOpen={(rel) => {
                  setFileRel(rel);
                  setMode("quicklook");
                  if (rel.endsWith(".png") || rel.endsWith(".svg"))
                    setFocus(rel);
                }}
              />
            ) : null}
          </div>
        </Panel>
        <Separator className="split" />
        <Panel id="center" minSize="30%">
          <div className="pane">
            {mode === "formal" ? (
              <p className="hint">{chrome.formalNote}</p>
            ) : null}
            {mode === "environment" ? <Environment /> : null}
            {mode === "quicklook" && run && fileRel ? (
              <FileView
                runId={run.run_id}
                rel={fileRel}
                onBack={() => setFileRel("")}
              />
            ) : null}
            {mode === "quicklook" && run && !fileRel ? (
              <StepDetail run={run} step={step} source={selected} />
            ) : null}
            {mode === "quicklook" && !run && bootstrap ? (
              <StartForm
                bootstrap={bootstrap}
                onStarted={(runId) => {
                  window.location.hash = `#/runs/${runId}`;
                }}
                onDemo={() => {
                  void startDemo()
                    .then((started) => {
                      window.location.hash = `#/runs/${started.run_id}`;
                    })
                    .catch((reason: unknown) => setError(errorText(reason)));
                }}
              />
            ) : null}
          </div>
        </Panel>
        <Separator className="split" />
        <Panel id="right" defaultSize="26%" minSize="16%">
          <div className="pane">
            <div className="tabs">
              <button
                type="button"
                className={right === "images" ? "on" : ""}
                onClick={() => setRight("images")}
              >
                {chrome.images}
              </button>
              <button
                type="button"
                className={right === "assistant" ? "on" : ""}
                onClick={() => setRight("assistant")}
              >
                {chrome.assistant}
              </button>
            </div>
            {right === "images" ? (
              <Images run={run} focus={focus} onFocus={setFocus} />
            ) : (
              <Assistant />
            )}
          </div>
        </Panel>
      </Group>
      <footer>
        {run ? (
          <>
            <span className="footer-item">
              {run.engine_name} {run.engine_version} ({run.engine_git})
            </span>
            <span className="footer-item">{run.output_root}</span>
            <span className="footer-item">{run.run_id}</span>
          </>
        ) : bootstrap ? (
          <span className="footer-item">
            {bootstrap.engine_name} {bootstrap.engine_version} (
            {bootstrap.engine_git})
          </span>
        ) : null}
      </footer>
    </div>
  );
}

function runIdFromHash(): string {
  const match = window.location.hash.match(/^#\/runs\/([0-9a-f]{16})$/);
  return match?.[1] ?? "";
}
