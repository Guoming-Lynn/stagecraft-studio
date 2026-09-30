import { useEffect, useState } from "react";

import {
  errorText,
  loadEnvironment,
  type EnvironmentReport,
} from "../api/client";
import { chrome } from "../text/chrome";

export function Environment() {
  const [report, setReport] = useState<EnvironmentReport | null>(null);
  const [message, setMessage] = useState("");
  useEffect(() => {
    let stop = false;
    void loadEnvironment()
      .then((next) => {
        if (!stop) setReport(next);
      })
      .catch((reason: unknown) => setMessage(errorText(reason)));
    return () => {
      stop = true;
    };
  }, []);
  return (
    <section className="detail">
      <h1>{chrome.environment}</h1>
      {message ? <p className="log-error">{message}</p> : null}
      <ul className="checks">
        {(report?.checks ?? []).map((item) => (
          <li key={item.name}>
            <strong>{item.detail}</strong>
            <span
              className={
                item.status === "pass" ? "mark mark-done" : "mark mark-failed"
              }
            >
              {item.label}
            </span>
            {item.fix ? <p className="hint">{item.fix}</p> : null}
          </li>
        ))}
      </ul>
    </section>
  );
}
