import { useState } from "react";

import {
  cancelRun,
  errorText,
  loadSteps,
  type Bootstrap,
  type RunListItem,
  type RunView,
  type StepView,
} from "../api/client";
import { noticePermission } from "../notify";
import {
  chrome,
  getLanguage,
  setLanguage,
  type Language,
} from "../text/chrome";

export type Mode = "quicklook" | "formal" | "environment" | "compare";

export function TopBar({
  bootstrap,
  runs,
  run,
  mode,
  onMode,
  onRun,
  onSteps,
  onError,
  onLanguageChange,
}: {
  bootstrap: Bootstrap | null;
  runs: RunListItem[];
  run: RunView | null;
  mode: Mode;
  onMode: (mode: Mode) => void;
  onRun: (run: RunView) => void;
  onSteps: (steps: StepView[]) => void;
  onError: (message: string) => void;
  onLanguageChange: () => void;
}) {
  const [permission, setPermission] = useState(noticePermission);
  const [language, setUiLanguage] = useState<Language>(getLanguage);
  const [theme, setTheme] = useState<"dark" | "light">(() => {
    if (typeof window !== "undefined") {
      const stored = localStorage.getItem("stagecraft_theme");
      if (stored === "light" || stored === "dark") return stored;
    }
    return "light";
  });

  const toggleTheme = () => {
    const next = theme === "dark" ? "light" : "dark";
    setTheme(next);
    if (typeof document !== "undefined") {
      document.documentElement.setAttribute("data-theme", next);
    }
    if (typeof localStorage !== "undefined") {
      localStorage.setItem("stagecraft_theme", next);
    }
  };

  return (
    <header className="topbar">
      <div className="brand">
        <svg
          className="brand-icon"
          viewBox="0 0 24 24"
          fill="none"
          stroke="currentColor"
          strokeWidth="2"
        >
          <circle cx="12" cy="12" r="3" />
          <path d="M19.07 4.93a10 10 0 0 1 0 14.14M4.93 4.93a10 10 0 0 0 0 14.14" />
        </svg>
        <span>Stagecraft</span>
        <span className="brand-badge">STUDIO</span>
      </div>
      <label>
        {chrome.project}
        <select
          value={run?.run_id ?? ""}
          onChange={(event) => {
            window.location.hash = event.target.value
              ? `#/runs/${event.target.value}`
              : "";
          }}
        >
          <option value="">{chrome.newRun}</option>
          {runs.map((item) => (
            <option key={item.run_id} value={item.run_id}>
              {item.run_id} · {item.status_label}
            </option>
          ))}
        </select>
      </label>
      <div className="topbar-nav">
        <label className="topbar-language">
          <span className="sr-only">{chrome.language}</span>
          <select
            aria-label={chrome.language}
            value={language}
            onChange={(event) => {
              const next = event.target.value as Language;
              setLanguage(next);
              setUiLanguage(next);
              onLanguageChange();
            }}
          >
            <option value="zh-CN">{chrome.languageZh}</option>
            <option value="en-US">{chrome.languageEn}</option>
          </select>
        </label>
        <button
          type="button"
          className={mode === "quicklook" ? "on" : ""}
          onClick={() => onMode("quicklook")}
        >
          {chrome.quicklook}
        </button>
        <button
          type="button"
          className={mode === "formal" ? "on" : ""}
          onClick={() => onMode("formal")}
        >
          {chrome.formal}
        </button>
        <button
          type="button"
          className={mode === "compare" ? "on" : ""}
          onClick={() => onMode("compare")}
        >
          {chrome.compareRuns}
        </button>
        <button
          type="button"
          onClick={() => {
            if (typeof Notification === "undefined") return;
            void Notification.requestPermission().then((next) =>
              setPermission(next),
            );
          }}
        >
          {permission === "granted" ? chrome.notifyOn : chrome.notify}
        </button>
        <button
          type="button"
          className={mode === "environment" ? "on" : ""}
          onClick={() => onMode("environment")}
        >
          {bootstrap?.environment_ok
            ? chrome.environmentOk
            : chrome.environmentBad}
        </button>
        <button
          type="button"
          disabled={!run?.can_cancel}
          onClick={() => {
            if (!run) return;
            void cancelRun(run.run_id)
              .then((next) => {
                onRun(next);
                return loadSteps(next.run_id).then(onSteps);
              })
              .catch((reason: unknown) => onError(errorText(reason)));
          }}
        >
          {chrome.cancel}
        </button>
        <button
          type="button"
          className="theme-toggle-btn"
          aria-label={theme === "dark" ? chrome.themeLight : chrome.themeDark}
          title={theme === "dark" ? chrome.themeLight : chrome.themeDark}
          onClick={toggleTheme}
        >
          {theme === "dark" ? (
            <svg
              width="14"
              height="14"
              viewBox="0 0 24 24"
              fill="none"
              stroke="currentColor"
              strokeWidth="2"
              strokeLinecap="round"
              strokeLinejoin="round"
            >
              <circle cx="12" cy="12" r="5" />
              <line x1="12" y1="1" x2="12" y2="3" />
              <line x1="12" y1="21" x2="12" y2="23" />
              <line x1="4.22" y1="4.22" x2="5.64" y2="5.64" />
              <line x1="18.36" y1="18.36" x2="19.78" y2="19.78" />
              <line x1="1" y1="12" x2="3" y2="12" />
              <line x1="21" y1="12" x2="23" y2="12" />
              <line x1="4.22" y1="19.78" x2="5.64" y2="18.36" />
              <line x1="18.36" y1="5.64" x2="19.78" y2="4.22" />
            </svg>
          ) : (
            <svg
              width="14"
              height="14"
              viewBox="0 0 24 24"
              fill="none"
              stroke="currentColor"
              strokeWidth="2"
              strokeLinecap="round"
              strokeLinejoin="round"
            >
              <path d="M21 12.79A9 9 0 1 1 11.21 3 7 7 0 0 0 21 12.79z" />
            </svg>
          )}
        </button>
      </div>
    </header>
  );
}
