import { useEffect, useState } from "react";

import { errorText, loadFile, mediaUrl } from "../api/client";
import { lineClass } from "../log_lines";
import { chrome } from "../text/chrome";
import { CsvView } from "./CsvView";

export function FileView({
  runId,
  rel,
  onBack,
}: {
  runId: string;
  rel: string;
  onBack: () => void;
}) {
  const kind = kindOf(rel);
  return (
    <section className="detail file-view-detail">
      <div className="file-view-header">
        <button type="button" className="btn-back" onClick={onBack}>
          {chrome.back}
        </button>
        <span className="file-view-tag">{kindLabel(kind)}</span>
      </div>
      <h1 className="file-view-title">{rel}</h1>
      {kind === "image" ? (
        <div className="file-img-frame">
          <img src={mediaUrl(runId, rel)} alt={rel} />
        </div>
      ) : null}
      {kind === "table" ? <CsvView runId={runId} rel={rel} /> : null}
      {kind === "text" ? (
        <TextPreview
          runId={runId}
          rel={rel}
          json={kind === "text" && rel.endsWith(".json")}
        />
      ) : null}
      {kind === "other" ? <p className="hint">{chrome.cannotPreview}</p> : null}
    </section>
  );
}

function TextPreview({
  runId,
  rel,
  json,
}: {
  runId: string;
  rel: string;
  json: boolean;
}) {
  const [text, setText] = useState("");
  const [note, setNote] = useState("");
  const [message, setMessage] = useState("");
  useEffect(() => {
    let stop = false;
    void loadFile(runId, rel)
      .then((preview) => {
        if (stop) return;
        setText(json ? pretty(preview.text) : preview.text);
        setNote(preview.note);
      })
      .catch((reason: unknown) => setMessage(errorText(reason)));
    return () => {
      stop = true;
    };
  }, [runId, rel, json]);
  if (message) return <p className="log-error">{message}</p>;
  if (rel.endsWith(".log")) {
    return (
      <div className="log">
        {text.split("\n").map((line, index) => (
          <div key={index} className={lineClass(line)}>
            {line}
          </div>
        ))}
      </div>
    );
  }
  return (
    <>
      {note ? <p className="hint">{note}</p> : null}
      <pre>{text}</pre>
    </>
  );
}

function pretty(text: string): string {
  try {
    return JSON.stringify(JSON.parse(text) as unknown, null, 2);
  } catch {
    return text;
  }
}

function kindLabel(kind: "image" | "table" | "text" | "other"): string {
  if (kind === "image") return chrome.kindImage;
  if (kind === "table") return chrome.kindTable;
  if (kind === "text") return chrome.kindText;
  return chrome.kindOther;
}

function kindOf(rel: string): "image" | "table" | "text" | "other" {
  const lower = rel.toLowerCase();
  if (lower.endsWith(".png") || lower.endsWith(".svg")) return "image";
  if (lower.endsWith(".csv") || lower.endsWith(".tsv")) return "table";
  if (
    lower.endsWith(".json") ||
    lower.endsWith(".log") ||
    lower.endsWith(".txt") ||
    lower.endsWith(".md")
  ) {
    return "text";
  }
  return "other";
}
