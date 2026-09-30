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
    const name = image.step_name || chrome.otherFigures;
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
              <div className="thumb-img-wrap">
                <img
                  src={mediaUrl(run.run_id, image.rel)}
                  alt={image.rel}
                  loading="lazy"
                />
              </div>
              <div className="thumb-meta">
                <span className="thumb-name">{image.rel.split("/").pop()}</span>
                <span
                  className={
                    image.passed ? "mark mark-done" : "mark mark-failed"
                  }
                >
                  {image.label}
                </span>
              </div>
              {image.reasons.map((reason) => (
                <span key={reason.code} className="reason">
                  {reason.text}。{chrome.suggestion}
                  {reason.suggestion}
                </span>
              ))}
            </button>
          ))}
        </section>
      ))}
      {open ? (
        <dialog open className="lightbox">
          <div className="lightbox-top">
            <strong>{open.rel}</strong>
            <button
              type="button"
              className="btn-close"
              onClick={() => {
                setCompare("");
                onFocus("");
              }}
            >
              {chrome.close}
            </button>
          </div>
          <div className="pair">
            <div className="img-frame">
              <img src={mediaUrl(run.run_id, open.rel)} alt={open.rel} />
            </div>
            {second ? (
              <div className="img-frame">
                <img src={mediaUrl(run.run_id, second.rel)} alt={second.rel} />
              </div>
            ) : null}
          </div>
          <p className="lightbox-label">{open.label}</p>
          <div className="lightbox-reasons">
            {open.reasons.map((reason) => (
              <p key={reason.code} className="reason">
                {reason.text}。{chrome.suggestion}
                {reason.suggestion}
              </p>
            ))}
          </div>
          <div className="lightbox-actions">
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
            <a href={mediaUrl(run.run_id, open.rel)} download>
              {chrome.download}
            </a>
          </div>
        </dialog>
      ) : null}
    </div>
  );
}
