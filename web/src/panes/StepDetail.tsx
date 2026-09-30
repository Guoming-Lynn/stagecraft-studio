import { useEffect, useRef, useState } from "react";

import type { RunView, SourceView, StepView } from "../api/client";
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
      <header>
        <h1>{run.heading}</h1>
        <p className="hint">{run.lede}</p>
        <p>{step ? `${step.name} · ${step.status_label}` : chrome.noRun}</p>
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
          <pre>{run.command_line}</pre>
          <button
            type="button"
            onClick={() => {
              void navigator.clipboard
                .writeText(run.command_line)
                .then(() => setCopied(true));
            }}
          >
            {copied ? chrome.copied : chrome.copyCommand}
          </button>
          <h2>{chrome.config}</h2>
          <CodeBlock code={run.config_text} lang="json" />
          <h2>{chrome.script}</h2>
          {source ? (
            <>
              <p className="hint">
                {source.script_name} · {source.engine_version}{" "}
                {source.engine_git} · {source.sha256}
              </p>
              <CodeBlock code={source.source} lang="python" />
            </>
          ) : (
            <p className="hint">{chrome.noRun}</p>
          )}
        </div>
      ) : null}
      {tab === "parameters" ? (
        <table>
          <tbody>
            {run.parameters.map((row) => (
              <tr key={row.name}>
                <th>{row.name}</th>
                <td>{row.value}</td>
                <td>{row.source_label}</td>
              </tr>
            ))}
          </tbody>
        </table>
      ) : null}
      {tab === "artifacts" ? (
        <ul>
          {(step?.artifacts ?? []).map((item) => (
            <li key={item.rel}>
              {item.rel} · {item.size} · {item.quality_label}
            </li>
          ))}
        </ul>
      ) : null}
    </section>
  );
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
        <div key={item.name}>
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
