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
}: {
  bootstrap: Bootstrap;
  onStarted: (runId: string) => void;
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
      <h1>{chrome.quicklook}</h1>
      <p className="hint">{bootstrap.group_note}</p>
      <label>
        {chrome.inputPath}
        <input
          value={inputPath}
          onChange={(event) => setInputPath(event.target.value)}
        />
      </label>
      <label>
        {chrome.gene}
        <input value={gene} onChange={(event) => setGene(event.target.value)} />
      </label>
      <label>
        {chrome.output}
        <input value={out} onChange={(event) => setOut(event.target.value)} />
      </label>
      <label>
        {chrome.gmt}
        <input value={gmt} onChange={(event) => setGmt(event.target.value)} />
      </label>
      <p className="readonly">{bootstrap.python}</p>
      <p className="readonly">{bootstrap.script}</p>
      <button
        type="button"
        onClick={() => {
          void inspectInput(form())
            .then(setFound)
            .catch((reason: unknown) => setMessage(errorText(reason)));
        }}
      >
        {chrome.inspect}
      </button>
      {found ? (
        <>
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
        </>
      ) : null}
      {message ? <p className="log-error">{message}</p> : null}
      <button type="submit">{chrome.start}</button>
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
      <select value={value} onChange={(event) => onChange(event.target.value)}>
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
      <select value={value} onChange={(event) => onChange(event.target.value)}>
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
