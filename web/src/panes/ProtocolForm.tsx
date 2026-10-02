import { useEffect, useState } from "react";

import {
  errorText,
  freezeProtocol,
  loadProtocolForm,
  type ProtocolField,
} from "../api/client";
import { chrome } from "../text/chrome";

type LibraryRow = { library_id: string; dataset: string };

export function ProtocolForm() {
  const [fields, setFields] = useState<ProtocolField[]>([]);
  const [gene, setGene] = useState("");
  const [species, setSpecies] = useState("human");
  const [harmony, setHarmony] = useState("dataset");
  const [minGenes, setMinGenes] = useState("200");
  const [dataPath, setDataPath] = useState("");
  const [libraries, setLibraries] = useState<LibraryRow[]>([
    { library_id: "", dataset: "" },
  ]);
  const [message, setMessage] = useState("");

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
      {libraries.map((row, index) => (
        <div key={index} className="row">
          <input
            value={row.library_id}
            placeholder={chrome.library}
            onChange={(event) =>
              setLibraries((current) =>
                current.map((item, itemIndex) =>
                  itemIndex === index
                    ? { ...item, library_id: event.target.value }
                    : item,
                ),
              )
            }
          />
          <input
            value={row.dataset}
            placeholder="dataset"
            onChange={(event) =>
              setLibraries((current) =>
                current.map((item, itemIndex) =>
                  itemIndex === index
                    ? { ...item, dataset: event.target.value }
                    : item,
                ),
              )
            }
          />
        </div>
      ))}
      <div className="row" style={{ gap: "8px" }}>
        <button
          type="button"
          onClick={() =>
            setLibraries((current) => [
              ...current,
              { library_id: "", dataset: "" },
            ])
          }
        >
          + {chrome.library}
        </button>
      </div>
      <button type="submit">{chrome.freeze}</button>
      {message ? <p className="hint">{message}</p> : null}
    </form>
  );
}
