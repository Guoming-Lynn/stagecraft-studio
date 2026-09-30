import { useState } from "react";

import {
  errorText,
  inspectInput,
  startRun,
  type Bootstrap,
  type InspectView,
  type QuicklookForm,
} from "../api/client";
import { chrome } from "../text/chrome";

export function StartForm({
  bootstrap,
  onStarted,
  onDemo,
}: {
  bootstrap: Bootstrap;
  onStarted: (runId: string) => void;
  onDemo: () => void;
}) {
  const [inputPath, setInputPath] = useState("");
  const [gene, setGene] = useState("");
  const [out, setOut] = useState("");
  const [gmt, setGmt] = useState(bootstrap.gmt);
  const [group, setGroup] = useState("");
  const [caseLabel, setCaseLabel] = useState("");
  const [controlLabel, setControlLabel] = useState("");
  const [batch, setBatch] = useState("");
  const [found, setFound] = useState<InspectView | null>(null);
  const [message, setMessage] = useState("");

  function form(): QuicklookForm {
    return {
      input_path: inputPath,
      gene,
      out,
      group,
      case_label: caseLabel,
      control_label: controlLabel,
      batch_column: batch,
      local_gmt: gmt,
    };
  }

  return (
    <form
      className="start"
      onSubmit={(event) => {
        event.preventDefault();
        void startRun(form())
          .then((started) => onStarted(started.run_id))
          .catch((reason: unknown) => setMessage(errorText(reason)));
      }}
    >
      <div className="form-header">
        <h1>{chrome.quicklook}</h1>
        <div className="form-callout">
          <p className="hint">{bootstrap.group_note}</p>
          <p className="hint">{bootstrap.demo_source}</p>
        </div>
      </div>

      <div className="form-section">
        <h2>{chrome.basicInputs}</h2>
        <div className="form-grid">
          <label>
            {chrome.inputPath}
            <input
              placeholder={chrome.inputPlaceholder}
              value={inputPath}
              onChange={(e) => setInputPath(e.target.value)}
            />
          </label>
          <label>
            {chrome.gene}
            <input
              placeholder={chrome.genePlaceholder}
              value={gene}
              onChange={(e) => setGene(e.target.value)}
            />
          </label>
          <label>
            {chrome.output}
            <input
              placeholder={chrome.outputPlaceholder}
              value={out}
              onChange={(e) => setOut(e.target.value)}
            />
          </label>
          <label>
            {chrome.gmt}
            <input
              placeholder={chrome.gmtPlaceholder}
              value={gmt}
              onChange={(e) => setGmt(e.target.value)}
            />
          </label>
        </div>
      </div>

      <div className="form-runtime">
        <span className="runtime-label">{chrome.runtime}</span>
        <p className="readonly">{bootstrap.python}</p>
        <p className="readonly">{bootstrap.script}</p>
      </div>

      <div className="form-section">
        <div className="inspect-row">
          <h2>{chrome.groupSection}</h2>
          <button
            type="button"
            className="btn-inspect"
            onClick={() => {
              void inspectInput(form())
                .then(setFound)
                .catch((reason: unknown) => setMessage(errorText(reason)));
            }}
          >
            {chrome.inspect}
          </button>
        </div>

        {found ? (
          <div className="form-grid group-grid">
            <Select
              label={chrome.group}
              value={group}
              blank={chrome.noneGroup}
              options={found.columns.map((column) => column.name)}
              onChange={setGroup}
            />
            <ValueSelect
              label={chrome.caseLabel}
              value={caseLabel}
              found={found}
              onChange={setCaseLabel}
            />
            <ValueSelect
              label={chrome.controlLabel}
              value={controlLabel}
              found={found}
              onChange={setControlLabel}
            />
            <Select
              label={chrome.batch}
              value={batch}
              blank={chrome.noneBatch}
              options={found.columns.map((column) => column.name)}
              onChange={setBatch}
            />
          </div>
        ) : null}
      </div>

      {message ? <p className="log-error">{message}</p> : null}

      <div className="form-actions">
        <button type="submit" className="btn-primary">
          {chrome.start}
        </button>
        <button type="button" className="btn-secondary" onClick={onDemo}>
          {chrome.demo}
        </button>
      </div>
    </form>
  );
}

function Select({
  label,
  value,
  blank,
  options,
  onChange,
}: {
  label: string;
  value: string;
  blank: string;
  options: string[];
  onChange: (value: string) => void;
}) {
  return (
    <label>
      {label}
      <select value={value} onChange={(e) => onChange(e.target.value)}>
        <option value="">{blank}</option>
        {options.map((option) => (
          <option key={option} value={option}>
            {option}
          </option>
        ))}
      </select>
    </label>
  );
}

function ValueSelect({
  label,
  value,
  found,
  onChange,
}: {
  label: string;
  value: string;
  found: InspectView;
  onChange: (value: string) => void;
}) {
  const rows = found.columns.flatMap((column) =>
    column.values.map((item) => ({
      value: item,
      label: `${column.name} · ${item}`,
    })),
  );
  return (
    <label>
      {label}
      <select value={value} onChange={(e) => onChange(e.target.value)}>
        <option value="">{chrome.noneValue}</option>
        {rows.map((row) => (
          <option key={row.label} value={row.value}>
            {row.label}
          </option>
        ))}
      </select>
    </label>
  );
}
