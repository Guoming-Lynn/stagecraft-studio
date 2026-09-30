import { useEffect, useRef, useState } from "react";

import {
  bundleUrl,
  type RunView,
  type SourceView,
  type StepView,
} from "../api/client";
import { lineClass, shouldFollowLog } from "../log_lines";
import { chrome } from "../text/chrome";
import { CodeBlock } from "./CodeBlock";

const TABS = ["log", "code", "parameters", "artifacts"] as const;

export function StepDetail({
  run,
  step,
  source,
}: {
  run: RunView;
  step: StepView | null;
  source: SourceView | null;
}) {
  const [tab, setTab] = useState<(typeof TABS)[number]>("log");
  const [copied, setCopied] = useState(false);
  return (
    <section className="detail">
      <header className="detail-header">
        <div className="detail-title-row">
          <h1>{run.heading}</h1>
          <span className={`mark mark-${run.status}`}>{run.status_label}</span>
        </div>
        <p className="hint">{run.lede}</p>
        <div className="current-step-chip">
          <span className="chip-label">{chrome.currentStep}</span>
          <strong>
            {step ? `${step.name} · ${step.status_label}` : chrome.noRun}
          </strong>
        </div>
        <dl className="status-row">
          <div>
            <dt>{chrome.engine}</dt>
            <dd>{run.status_label}</dd>
          </div>
          <div>
            <dt>{chrome.input}</dt>
            <dd>{run.pipeline_label}</dd>
          </div>
          <div>
            <dt>{chrome.quality}</dt>
            <dd>{run.figure_label}</dd>
          </div>
          <div>
            <dt>{chrome.enrichment}</dt>
            <dd>{run.enrichment_label}</dd>
          </div>
        </dl>
        <h2>{chrome.methodsHeading}</h2>
        <p className="methods">{run.methods_text}</p>
        <p>
          <a href={bundleUrl(run.run_id)}>{chrome.bundle}</a>
        </p>
      </header>
      <div className="tabs">
        {TABS.map((item) => (
          <button
            key={item}
            type="button"
            className={tab === item ? "on" : ""}
            onClick={() => setTab(item)}
          >
            {chrome[item]}
          </button>
        ))}
      </div>
      {tab === "log" ? <LogPane run={run} /> : null}
      {tab === "code" ? (
        <div className="stack">
          <h2>{chrome.argv}</h2>
          <div className="code-box">
            <pre>{run.command_line}</pre>
            <button
              type="button"
              className="copy-btn"
              onClick={() => {
                void navigator.clipboard
                  .writeText(run.command_line)
                  .then(() => setCopied(true));
              }}
            >
              {copied ? chrome.copied : chrome.copyCommand}
            </button>
          </div>
          <h2>{chrome.config}</h2>
          <CodeBlock code={run.config_text} lang="json" />
          <h2>{chrome.script}</h2>
          {source ? (
            <>
              <div className="metadata-tag">
                <span>{source.script_name}</span>
                <span>
                  {source.engine_version} ({source.engine_git})
                </span>
                <code>{source.sha256}</code>
              </div>
              <CodeBlock code={source.source} lang="python" />
            </>
          ) : (
            <p className="hint">{chrome.noRun}</p>
          )}
        </div>
      ) : null}
      {tab === "parameters" ? (
        <table className="param-table">
          <thead>
            <tr>
              <th>{chrome.parameter}</th>
              <th>{chrome.value}</th>
              <th>{chrome.source}</th>
            </tr>
          </thead>
          <tbody>
            {run.parameters.map((row) => (
              <tr key={row.name}>
                <th>{row.name}</th>
                <td>
                  <code>{row.value}</code>
                </td>
                <td>
                  <span
                    className={`mark mark-source mark-source-${row.source}`}
                  >
                    {row.source_label}
                  </span>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      ) : null}
      {tab === "artifacts" ? (
        <ul className="artifact-list">
          {(step?.artifacts ?? []).map((item) => (
            <li key={item.rel} className="artifact-item">
              <span className="artifact-rel">{item.rel}</span>
              <span className="artifact-size">{item.size}</span>
              <span className={qualityClass(item.quality_status)}>
                {item.quality_label}
              </span>
            </li>
          ))}
        </ul>
      ) : null}
    </section>
  );
}

function qualityClass(status: string): string {
  if (status === "pass") return "mark mark-done";
  if (status === "fail") return "mark mark-failed";
  return "mark";
}

function LogPane({ run }: { run: RunView }) {
  const box = useRef<HTMLDivElement>(null);
  const follow = useRef(true);
  const text = run.logs.map((item) => item.text).join("\n");
  useEffect(() => {
    const node = box.current;
    if (!node || !follow.current) return;
    if (run.status === "failed") {
      node.querySelector(".log-error")?.scrollIntoView({ block: "nearest" });
      return;
    }
    node.scrollTop = node.scrollHeight;
  }, [text, run.status]);
  if (run.logs.length === 0) return <p className="hint">{chrome.noLog}</p>;
  return (
    <div
      className="log"
      ref={box}
      onScroll={() => {
        if (box.current) follow.current = shouldFollowLog(box.current);
      }}
    >
      {run.logs.map((item) => (
        <div key={item.name} className="log-section">
          <p className="log-name">{item.name}</p>
          {item.text.split("\n").map((line, index) => (
            <div key={`${item.name}-${index}`} className={lineClass(line)}>
              {line}
            </div>
          ))}
        </div>
      ))}
    </div>
  );
}
