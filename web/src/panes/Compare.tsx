import { useEffect, useState } from "react";

import {
  errorText,
  loadCompare,
  type CompareView,
  type RunListItem,
} from "../api/client";
import { chrome } from "../text/chrome";

export function Compare({ runs }: { runs: RunListItem[] }) {
  const [left, setLeft] = useState("");
  const [right, setRight] = useState("");
  const [view, setView] = useState<CompareView | null>(null);
  const [message, setMessage] = useState("");

  useEffect(() => {
    if (!left && runs[0]) setLeft(runs[0].run_id);
    if (!right && runs[1]) setRight(runs[1].run_id);
  }, [runs, left, right]);

  useEffect(() => {
    if (!left || !right) return;
    let stop = false;
    void loadCompare(left, right)
      .then((next) => {
        if (!stop) {
          setView(next);
          setMessage("");
        }
      })
      .catch((reason: unknown) => {
        if (!stop) setMessage(errorText(reason));
      });
    return () => {
      stop = true;
    };
  }, [left, right]);

  return (
    <section className="detail">
      <h1>{chrome.compareRuns}</h1>
      <div className="form-grid">
        <label>
          {chrome.leftRun}
          <select
            value={left}
            onChange={(event) => setLeft(event.target.value)}
          >
            <option value="">{chrome.noneValue}</option>
            {runs.map((item) => (
              <option key={item.run_id} value={item.run_id}>
                {item.run_id} {item.status_label}
              </option>
            ))}
          </select>
        </label>
        <label>
          {chrome.rightRun}
          <select
            value={right}
            onChange={(event) => setRight(event.target.value)}
          >
            <option value="">{chrome.noneValue}</option>
            {runs.map((item) => (
              <option key={item.run_id} value={item.run_id}>
                {item.run_id} {item.status_label}
              </option>
            ))}
          </select>
        </label>
      </div>
      {message ? <p className="log-error">{message}</p> : null}
      {view ? <CompareBody view={view} /> : null}
    </section>
  );
}

function CompareBody({ view }: { view: CompareView }) {
  return (
    <>
      <table className="param-table">
        <thead>
          <tr>
            <th>{chrome.parameter}</th>
            <th>{view.left_id}</th>
            <th>{view.right_id}</th>
          </tr>
        </thead>
        <tbody>
          <tr>
            <th>{chrome.cells}</th>
            <td>{view.cells_left}</td>
            <td>{view.cells_right}</td>
          </tr>
          <tr>
            <th>{chrome.clusters}</th>
            <td>{view.clusters_left}</td>
            <td>{view.clusters_right}</td>
          </tr>
          <tr>
            <th>{chrome.quality}</th>
            <td>{view.figure_left}</td>
            <td>{view.figure_right}</td>
          </tr>
          {view.parameters.map((row) => (
            <tr key={row.name} className={row.same ? "" : "compare-diff"}>
              <th>{row.name}</th>
              <td>{row.left}</td>
              <td>{row.right}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </>
  );
}
