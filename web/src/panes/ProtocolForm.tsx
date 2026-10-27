import { useEffect, useState } from "react";

import {
  errorText,
  freezeProtocol,
  loadProtocolForm,
  type ProtocolField,
} from "../api/client";
import { takeProposal } from "../proposal_store";
import { chrome } from "../text/chrome";

type LibraryRow = {
  library_id: string;
  dataset: string;
  donor_id: string;
  source_block: string;
};

const LIBRARY_COLUMNS: [keyof LibraryRow, string][] = [
  ["library_id", chrome.library],
  ["dataset", "dataset"],
  ["donor_id", "donor_id"],
  ["source_block", "source_block"],
];

const emptyRow = (): LibraryRow => ({
  library_id: "",
  dataset: "",
  donor_id: "",
  source_block: "",
});

export function ProtocolForm() {
  const [fields, setFields] = useState<ProtocolField[]>([]);
  const [gene, setGene] = useState("");
  const [species, setSpecies] = useState("human");
  const [harmony, setHarmony] = useState("dataset");
  const [minGenes, setMinGenes] = useState("200");
  const [dataPath, setDataPath] = useState("");
  const [libraries, setLibraries] = useState<LibraryRow[]>([emptyRow()]);
  const [message, setMessage] = useState("");

  useEffect(() => {
    const apply = () => {
      const values = takeProposal();
      if (!values || !("target_gene" in values)) return;
      setGene(values.target_gene);
      setSpecies(values.species);
      setHarmony(values.harmony_keys.join(", "));
      setMinGenes(String(values.loose_min_genes));
      setMessage(chrome.assistantProposalApplied);
    };
    apply();
    window.addEventListener("stagecraft:apply-proposal", apply);
    return () => window.removeEventListener("stagecraft:apply-proposal", apply);
  }, []);

  useEffect(() => {
    void loadProtocolForm()
      .then((form) => setFields(form.fields))
      .catch((reason: unknown) => setMessage(errorText(reason)));
  }, []);

  const help = (name: string) => fields.find((field) => field.name === name);

  return (
    <form
      className="stack"
      onSubmit={(event) => {
        event.preventDefault();
        void freezeProtocol({
          target_gene: gene,
          species,
          harmony_keys: harmony
            .split(",")
            .map((item) => item.trim())
            .filter((item) => item.length > 0),
          loose_min_genes: Number(minGenes),
          data_path: dataPath,
          libraries,
        })
          .then((frozen) => setMessage(frozen.content_hash))
          .catch((reason: unknown) => setMessage(errorText(reason)));
      }}
    >
      <h2>{chrome.design}</h2>
      <label>
        {chrome.gene}
        <input value={gene} onChange={(event) => setGene(event.target.value)} />
        <span className="hint">{help("target_gene")?.freeze_impact}</span>
      </label>
      <label>
        {chrome.organism}
        <select
          value={species}
          onChange={(event) => setSpecies(event.target.value)}
        >
          <option value="human">{chrome.organismHuman}</option>
          <option value="mouse">{chrome.organismMouse}</option>
        </select>
        <span className="hint">{help("species")?.reason}</span>
      </label>
      <label>
        {chrome.harmony}
        <input
          value={harmony}
          onChange={(event) => setHarmony(event.target.value)}
        />
        <span className="hint">{help("harmony_keys")?.reason}</span>
      </label>
      <label>
        {chrome.minGenes}
        <input
          value={minGenes}
          onChange={(event) => setMinGenes(event.target.value)}
        />
        <span className="hint">{help("loose_min_genes")?.freeze_impact}</span>
      </label>
      <label>
        {chrome.inputPath}
        <input
          value={dataPath}
          onChange={(event) => setDataPath(event.target.value)}
        />
        <span className="hint">{help("data_path")?.reason}</span>
      </label>
      <div className="card" style={{ gap: "8px" }}>
        <div className="row spread">
          <h4>{chrome.library}</h4>
          <span className="hint">{help("libraries")?.reason}</span>
        </div>
        <table>
          <thead>
            <tr>
              {LIBRARY_COLUMNS.map(([key, label]) => (
                <th key={key}>{label}</th>
              ))}
            </tr>
          </thead>
          <tbody>
            {libraries.map((row, index) => (
              <tr key={index}>
                {LIBRARY_COLUMNS.map(([key, placeholder]) => (
                  <td key={key}>
                    <input
                      style={{ width: "100%" }}
                      value={row[key]}
                      placeholder={placeholder}
                      onChange={(event) =>
                        setLibraries((current) =>
                          current.map((item, itemIndex) =>
                            itemIndex === index
                              ? { ...item, [key]: event.target.value }
                              : item,
                          ),
                        )
                      }
                    />
                  </td>
                ))}
              </tr>
            ))}
          </tbody>
        </table>
        <div>
          <button
            type="button"
            onClick={() => setLibraries((current) => [...current, emptyRow()])}
          >
            + {chrome.library}
          </button>
        </div>
      </div>
      <button type="submit">{chrome.freeze}</button>
      {message ? <p className="hint">{message}</p> : null}
    </form>
  );
}
