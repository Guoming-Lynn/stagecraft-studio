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
      <button type="button" onClick={onReveal}>
        {chrome.reveal}
      </button>
      <ul>
        {entries.map((entry) => (
          <li
            key={entry.rel}
            style={{ paddingLeft: `${entry.rel.split("/").length * 0.6}rem` }}
          >
            {entry.kind === "file" ? (
              <button
                type="button"
                className="link"
                onClick={() => onOpen(entry.rel)}
              >
                {entry.rel.split("/").pop()}
              </button>
            ) : (
              <span>{entry.rel.split("/").pop()}</span>
            )}
          </li>
        ))}
      </ul>
    </div>
  );
}
