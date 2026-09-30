import type { TreeEntry } from "../api/client";
import { chrome } from "../text/chrome";

export function Files({
  entries,
  onReveal,
  onOpen,
}: {
  entries: TreeEntry[];
  onReveal: () => void;
  onOpen: (rel: string) => void;
}) {
  return (
    <div className="files">
      <button type="button" className="btn-reveal" onClick={onReveal}>
        {chrome.reveal}
      </button>
      <ul>
        {entries.map((entry) => {
          const depth = entry.rel.split("/").length;
          const name = entry.rel.split("/").pop();
          return (
            <li
              key={entry.rel}
              style={{ paddingLeft: `${(depth - 1) * 0.85}rem` }}
            >
              {entry.kind === "file" ? (
                <button
                  type="button"
                  className="link file-item"
                  onClick={() => onOpen(entry.rel)}
                >
                  <span className="file-name">{name}</span>
                </button>
              ) : (
                <span className="dir-item">
                  <span className="file-name">{name}</span>
                </span>
              )}
            </li>
          );
        })}
      </ul>
    </div>
  );
}
