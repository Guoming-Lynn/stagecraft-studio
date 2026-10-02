import { chrome } from "../text/chrome";

export type S2Row = {
  cluster: string;
  decision: "KEEP" | "DELETE";
  rationale: string;
};

export type S3Row = {
  cluster: string;
  name: string;
  rationale: string;
};

export function Stop2Table({
  rows,
  onChange,
}: {
  rows: S2Row[];
  onChange: (update: (curr: S2Row[]) => S2Row[]) => void;
}) {
  return (
    <table>
      <thead>
        <tr>
          <th>{chrome.reviewClusters}</th>
          <th>{chrome.keep}</th>
          <th>依据</th>
        </tr>
      </thead>
      <tbody>
        {rows.map((r) => (
          <tr key={r.cluster}>
            <td>{r.cluster}</td>
            <td>
              <select
                value={r.decision}
                onChange={(e) => {
                  const dec = e.target.value === "DELETE" ? "DELETE" : "KEEP";
                  onChange((c) =>
                    c.map((it) =>
                      it.cluster === r.cluster ? { ...it, decision: dec } : it,
                    ),
                  );
                }}
              >
                <option value="KEEP">{chrome.keep}</option>
                <option value="DELETE">{chrome.delete}</option>
              </select>
            </td>
            <td>
              <input
                value={r.rationale}
                placeholder="依据"
                onChange={(e) =>
                  onChange((c) =>
                    c.map((it) =>
                      it.cluster === r.cluster
                        ? { ...it, rationale: e.target.value }
                        : it,
                    ),
                  )
                }
              />
            </td>
          </tr>
        ))}
      </tbody>
    </table>
  );
}

export function Stop3Table({
  rows,
  onChange,
}: {
  rows: S3Row[];
  onChange: (update: (curr: S3Row[]) => S3Row[]) => void;
}) {
  return (
    <table>
      <thead>
        <tr>
          <th>{chrome.reviewClusters}</th>
          <th>{chrome.name}</th>
          <th>依据</th>
        </tr>
      </thead>
      <tbody>
        {rows.map((r) => (
          <tr key={r.cluster}>
            <td>{r.cluster}</td>
            <td>
              <input
                value={r.name}
                placeholder="亚型命名（禁止含目标基因）"
                onChange={(e) =>
                  onChange((c) =>
                    c.map((it) =>
                      it.cluster === r.cluster
                        ? { ...it, name: e.target.value }
                        : it,
                    ),
                  )
                }
              />
            </td>
            <td>
              <input
                value={r.rationale}
                placeholder="依据"
                onChange={(e) =>
                  onChange((c) =>
                    c.map((it) =>
                      it.cluster === r.cluster
                        ? { ...it, rationale: e.target.value }
                        : it,
                    ),
                  )
                }
              />
            </td>
          </tr>
        ))}
      </tbody>
    </table>
  );
}
