import { useState } from "react";

import { mediaUrl, type RunView } from "../api/client";
import { chrome } from "../text/chrome";

export function Images({
  run,
  focus,
  onFocus,
}: {
  run: RunView | null;
  focus: string;
  onFocus: (rel: string) => void;
}) {
  const [compare, setCompare] = useState("");
  if (!run || run.images.length === 0)
    return <p className="hint">{chrome.noImage}</p>;
  const groups = new Map<string, RunView["images"]>();
  for (const image of run.images) {
    const name = image.step_name || "其他";
    const rows = groups.get(name) ?? [];
    rows.push(image);
    groups.set(name, rows);
  }
  const open = run.images.find((image) => image.rel === focus) ?? null;
  const second = run.images.find((image) => image.rel === compare) ?? null;
  return (
    <div className="images">
      {[...groups.entries()].map(([name, images]) => (
        <section key={name}>
          <h3>{name}</h3>
          {images.map((image) => (
            <button
              key={image.rel}
              type="button"
              className="thumb"
              onClick={() => onFocus(image.rel)}
            >
              <img src={mediaUrl(run.run_id, image.rel)} alt={image.rel} />
              <span
                className={image.passed ? "mark mark-done" : "mark mark-failed"}
              >
                {image.label}
              </span>
              {image.reasons.map((reason) => (
                <span key={reason.code} className="reason">
                  {reason.text}。建议：{reason.suggestion}
                </span>
              ))}
            </button>
          ))}
        </section>
      ))}
      {open ? (
        <dialog open className="lightbox">
          <div className="pair">
            <img src={mediaUrl(run.run_id, open.rel)} alt={open.rel} />
            {second ? (
              <img src={mediaUrl(run.run_id, second.rel)} alt={second.rel} />
            ) : null}
          </div>
          <p>{open.label}</p>
          {open.reasons.map((reason) => (
            <p key={reason.code}>
              {reason.text}。建议：{reason.suggestion}
            </p>
          ))}
          <a href={mediaUrl(run.run_id, open.rel)} download>
            {chrome.download}
          </a>
          <select
            value={compare}
            onChange={(event) => setCompare(event.target.value)}
          >
            <option value="">{chrome.compare}</option>
            {run.images
              .filter((image) => image.rel !== open.rel)
              .map((image) => (
                <option key={image.rel} value={image.rel}>
                  {image.rel}
                </option>
              ))}
          </select>
          <button
            type="button"
            onClick={() => {
              setCompare("");
              onFocus("");
            }}
          >
            {chrome.close}
          </button>
        </dialog>
      ) : null}
    </div>
  );
}
