import fs from "node:fs";
import os from "node:os";
import path from "node:path";
import { fileURLToPath } from "node:url";

import { defineConfig } from "@playwright/test";

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");
const engine = path.join(os.tmpdir(), "stagecraft-studio-e2e");
const formalScripts = path.join(engine, "formal_scripts");
const formalProject = path.join(engine, "formal_project");
const formalInput = path.join(formalProject, "synthetic_counts.h5ad");
const python =
  process.platform === "win32"
    ? path.join(root, ".venv", "Scripts", "python.exe")
    : path.join(root, ".venv", "bin", "python");
const script = path.join(engine, "run_pipeline.py");
const state = path.join(engine, "runs.json");

const DEMO_WRITER = `import json
import sys
from pathlib import Path

args = sys.argv[1:]
out = Path(args[args.index("--out") + 1])
out.write_bytes(b"h5ad")
sys.stdout.write(
    json.dumps(
        {
            "source": "合成矩阵，由 write_demo_h5ad.py 用种子 42 生成。不是策展数据，不能当作正式分析。",
            "gene": "IFITM3",
            "group": "group",
            "case": "Disease",
            "control": "Healthy",
            "batch": "sample_id",
        }
    )
    + "\\n"
)
raise SystemExit(0)
`;

const PIPELINE = `import base64
import json
import sys
from pathlib import Path

args = sys.argv[1:]
config = json.loads(Path(args[args.index("--config") + 1]).read_text(encoding="utf-8"))
out = Path(config["OUTPUT_ROOT"])
figures = out / "04_figures"
figures.mkdir(parents=True, exist_ok=True)
png = base64.b64decode(
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8z8BQDwAEhQGAhKmMIQAAAABJRU5ErkJggg=="
)
(figures / "volcano.png").write_bytes(png)
logs = out / "99_logs"
logs.mkdir(parents=True, exist_ok=True)
(logs / "pipeline_status.json").write_text(
    json.dumps({"outcome": "completed_analysis"}), encoding="utf-8"
)
(logs / "figure_quality_dataset_report.json").write_text(
    json.dumps({"status": "pass", "bad_figures": []}), encoding="utf-8"
)
raise SystemExit(0)
`;

fs.mkdirSync(engine, { recursive: true });
fs.mkdirSync(formalScripts, { recursive: true });
fs.mkdirSync(formalProject, { recursive: true });
fs.writeFileSync(path.join(engine, "write_demo_h5ad.py"), DEMO_WRITER, "utf8");
fs.writeFileSync(script, PIPELINE, "utf8");
fs.writeFileSync(formalInput, "synthetic-e2e-counts", "utf8");
fs.writeFileSync(
  path.join(formalProject, "qc_config.json"),
  JSON.stringify({ random_seed: 42 }),
  "utf8",
);
fs.writeFileSync(
  path.join(formalProject, "grid_config.json"),
  JSON.stringify({ random_seed: 42 }),
  "utf8",
);

const ONE_PIXEL_PNG =
  "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8z8BQDwAEhQGAhKmMIQAAAABJRU5ErkJggg==";

const FORMAL_STUBS: Record<string, string> = {
  "part1_load.py": `import argparse, json, pathlib
p = argparse.ArgumentParser()
p.add_argument("--library-id", default="L1")
p.add_argument("--out", type=pathlib.Path, required=True)
a, _ = p.parse_known_args()
a.out.mkdir(parents=True, exist_ok=True)
(a.out / "loaded.h5ad").write_text("loaded\\n", encoding="utf-8")
(a.out / "symbol_audit.csv").write_text("raw_symbol,collapsed_symbol\\nSTAT1,STAT1\\n", encoding="utf-8")
(a.out / "donor_audit.json").write_text(json.dumps({"library_id": a.library_id, "donor_source": "obs_donor_id", "donor_count": 2}), encoding="utf-8")
`,
  "part1_qc.py": `import argparse, json, pathlib
p = argparse.ArgumentParser()
p.add_argument("--library-id", default="L1")
p.add_argument("--out", type=pathlib.Path, required=True)
a, _ = p.parse_known_args()
a.out.mkdir(parents=True, exist_ok=True)
(a.out / "clean.h5ad").write_text("clean\\n", encoding="utf-8")
(a.out / "qc_record.json").write_text(json.dumps({"library_id": a.library_id, "scrublet_status": "ok", "in_primary_atlas": True, "n_singlets": 60, "mad_bounds": {"n_genes": [200, 2000]}}), encoding="utf-8")
`,
  "part1_merge.py": `import argparse, pathlib
p = argparse.ArgumentParser()
p.add_argument("--out", type=pathlib.Path, required=True)
a, _ = p.parse_known_args()
a.out.mkdir(parents=True, exist_ok=True)
for name in ("all_context_union.h5ad", "primary_union.h5ad", "primary_common.h5ad"):
    (a.out / name).write_text("merged\\n", encoding="utf-8")
(a.out / "gene_presence_by_dataset.csv").write_text("dataset,gene,n_libraries_in_dataset,n_libraries_present,present_in_any,present_in_all,in_strict_common\\nD1,STAT1,1,1,True,True,True\\n", encoding="utf-8")
`,
  "part1_resolution_grid.py": `import argparse, base64, json, pathlib
p = argparse.ArgumentParser()
p.add_argument("--out", type=pathlib.Path, required=True)
a, _ = p.parse_known_args()
a.out.mkdir(parents=True, exist_ok=True)
(a.out / "Leiden_resolution_overview.csv").write_text("resolution,n_clusters,min_cluster_size,median_cluster_size,max_cluster_size\\n0.4,2,25,30,35\\n", encoding="utf-8")
(a.out / "cluster_by_dataset.csv").write_text("resolution,cluster,dataset,n_cells\\n0.4,0,D1,35\\n0.4,1,D1,25\\n", encoding="utf-8")
(a.out / "pca_audit.csv").write_text("pc,variance_ratio\\n1,0.25\\n", encoding="utf-8")
(a.out / "grid_record.json").write_text(json.dumps({"resolutions": ["0.4"]}), encoding="utf-8")
(a.out / "leiden_resolution_overview.png").write_bytes(base64.b64decode("${ONE_PIXEL_PNG}"))
(a.out / "all_resolutions.h5ad").write_text("grid\\n", encoding="utf-8")
`,
  "part1_round.py": `import argparse, base64, json, pathlib
p = argparse.ArgumentParser()
p.add_argument("--round-index", type=int, default=1)
p.add_argument("--out", type=pathlib.Path, required=True)
a, _ = p.parse_known_args()
a.out.mkdir(parents=True, exist_ok=True)
(a.out / "Leiden_resolution_overview.csv").write_text("resolution,n_clusters,min_cluster_size,median_cluster_size,max_cluster_size\\n0.4,1,35,35,35\\n", encoding="utf-8")
(a.out / "cluster_by_dataset.csv").write_text("resolution,cluster,dataset,n_cells\\n0.4,0,D1,35\\n", encoding="utf-8")
(a.out / "pca_audit.csv").write_text("pc,variance_ratio\\n1,0.3\\n", encoding="utf-8")
(a.out / "grid_record.json").write_text(json.dumps({"resolutions": ["0.4"]}), encoding="utf-8")
(a.out / "leiden_resolution_overview.png").write_bytes(base64.b64decode("${ONE_PIXEL_PNG}"))
(a.out / "all_resolutions.h5ad").write_text("round\\n", encoding="utf-8")
(a.out / "retained_common.h5ad").write_text("retained\\n", encoding="utf-8")
(a.out / "round_record.json").write_text(json.dumps({"round_index": a.round_index}), encoding="utf-8")
`,
  "cluster_review_tables.py": `import argparse, json, pathlib
p = argparse.ArgumentParser()
p.add_argument("--resolution", default="0.4")
p.add_argument("--round-index", type=int, default=0)
p.add_argument("--out", type=pathlib.Path, required=True)
a, _ = p.parse_known_args()
a.out.mkdir(parents=True, exist_ok=True)
(a.out / "review_table.json").write_text("{}\\n", encoding="utf-8")
(a.out / "selected_tables.json").write_text(json.dumps({"resolution": a.resolution, "round_index": a.round_index}), encoding="utf-8")
(a.out / "selected_cluster_qc.csv").write_text("cluster,n_cells,n_donors,n_datasets,n_libraries,p5_total_counts,p25_total_counts,median_total_counts,p75_total_counts,p95_total_counts,p5_n_genes,p25_n_genes,median_n_genes,p75_n_genes,p95_n_genes,p5_pct_mt,p25_pct_mt,median_pct_mt,p75_pct_mt,p95_pct_mt\\n0,35,2,1,1,500,750,1000,1250,1500,200,300,400,500,600,1,3,5,7,9\\n1,25,2,1,1,250,375,500,625,750,100,150,200,250,300,2,5,8,11,15\\n", encoding="utf-8")
(a.out / "selected_top20_by_cluster.csv").write_text("cluster,top20_markers\\n0,LYZ;FCER1G\\n1,CD3D;CD3E\\n", encoding="utf-8")
(a.out / "selected_markers.csv").write_text("cluster,rank,gene,logfoldchange,pct_in,pct_out,pct_delta,marker_quality,quality_basis\\n0,1,LYZ,1.2,0.8,0.1,0.7,STRONG,thresholds\\n1,1,CD3D,0.9,0.7,0.1,0.6,STRONG,thresholds\\n", encoding="utf-8")
`,
  "part1_lock.py": `import argparse, json, pathlib
p = argparse.ArgumentParser()
p.add_argument("--out", type=pathlib.Path, required=True)
a, _ = p.parse_known_args()
a.out.mkdir(parents=True, exist_ok=True)
(a.out / "locked_atlas.h5ad").write_text("locked\\n", encoding="utf-8")
(a.out / "celltype_colors.yaml").write_text("Monocyte: '#2f6f5e'\\n", encoding="utf-8")
(a.out / "cluster_mapping.csv").write_text("cluster,name\\n0,Monocyte\\n1,T_cell\\n", encoding="utf-8")
(a.out / "lock_record.json").write_text(json.dumps({"locked": True}), encoding="utf-8")
`,
  "part2_survey.py": `import argparse, json, pathlib
p = argparse.ArgumentParser()
p.add_argument("--out", type=pathlib.Path, required=True)
a, _ = p.parse_known_args()
a.out.mkdir(parents=True, exist_ok=True)
(a.out / "group_summary.csv").write_text("group,n_cells\\nMonocyte,35\\n", encoding="utf-8")
(a.out / "unit_by_group.csv").write_text("dataset_donor_id,group,n_cells\\nD1_P1,Monocyte,35\\n", encoding="utf-8")
(a.out / "lodo_detection.csv").write_text("fold,detected\\nD1,True\\n", encoding="utf-8")
(a.out / "part2_record.json").write_text(json.dumps({"gene": "STAT1"}), encoding="utf-8")
`,
  "part2_figures.py": `import argparse, base64, json, pathlib
p = argparse.ArgumentParser()
p.add_argument("--out", type=pathlib.Path, required=True)
a, _ = p.parse_known_args()
a.out.mkdir(parents=True, exist_ok=True)
(a.out / "F02_target_dotplot.png").write_bytes(base64.b64decode("${ONE_PIXEL_PNG}"))
(a.out / "part2_figure_record.json").write_text(json.dumps({"figures": ["F02_target_dotplot.png"]}), encoding="utf-8")
`,
  "part3_recluster.py": `import argparse, json, pathlib
p = argparse.ArgumentParser()
p.add_argument("--out", type=pathlib.Path, required=True)
a, _ = p.parse_known_args()
a.out.mkdir(parents=True, exist_ok=True)
(a.out / "compartment_counts.h5ad").write_text("comp\\n", encoding="utf-8")
(a.out / "part3_record.json").write_text(json.dumps({"lineage": "Myeloid"}), encoding="utf-8")
(a.out / "grid_record.json").write_text(json.dumps({"resolutions": ["0.4"]}), encoding="utf-8")
`,
  "part4_survey.py": `import argparse, json, pathlib
p = argparse.ArgumentParser()
p.add_argument("--out", type=pathlib.Path, required=True)
a, _ = p.parse_known_args()
a.out.mkdir(parents=True, exist_ok=True)
(a.out / "part4_record.json").write_text(json.dumps({"flag": "RANGE_OK"}), encoding="utf-8")
`,
  "part4_figures.py": `import argparse, json, pathlib
p = argparse.ArgumentParser()
p.add_argument("--out", type=pathlib.Path, required=True)
a, _ = p.parse_known_args()
a.out.mkdir(parents=True, exist_ok=True)
(a.out / "part4_figure_record.json").write_text(json.dumps({"figures": []}), encoding="utf-8")
`,
  "part5_prepare.py": `import argparse, json, pathlib
p = argparse.ArgumentParser()
p.add_argument("--out", type=pathlib.Path, required=True)
a, _ = p.parse_known_args()
a.out.mkdir(parents=True, exist_ok=True)
(a.out / "metadata.csv").write_text("dataset_donor_id,donor_id\\nD1_P1,P1\\n", encoding="utf-8")
(a.out / "genes.csv").write_text("gene\\nSTAT1\\n", encoding="utf-8")
(a.out / "outcome_counts.mtx").write_text("%%MatrixMarket matrix coordinate integer general\\n1 1 1\\n1 1 5\\n", encoding="utf-8")
(a.out / "source_block_suggestions.csv").write_text("dataset,source_block\\nD1,S1\\n", encoding="utf-8")
(a.out / "eligibility.csv").write_text("arm,eligibility\\nMonocyte,NOT_ESTIMABLE\\n", encoding="utf-8")
(a.out / "verdict.json").write_text(json.dumps({"eligibility": "NOT_ESTIMABLE", "stopped": "NOT_ESTIMABLE", "reason": "insufficient_donors_in_synthetic_fixture", "rdf": 0, "design_rank": 1, "design_columns": 2}), encoding="utf-8")
`,
  "stage_report.py": `import argparse, pathlib
p = argparse.ArgumentParser()
p.add_argument("--stage", type=pathlib.Path, required=False)
p.add_argument("--out", type=pathlib.Path, required=True)
a, _ = p.parse_known_args()
a.out.parent.mkdir(parents=True, exist_ok=True)
a.out.write_text("# Synthetic Formal Stage Report\\n", encoding="utf-8")
`,
};

for (const [name, content] of Object.entries(FORMAL_STUBS)) {
  fs.writeFileSync(path.join(formalScripts, name), content, "utf8");
}

function serverEnv(statePath: string): Record<string, string> {
  const found: Record<string, string> = {};
  for (const [key, value] of Object.entries(process.env)) {
    if (value !== undefined) found[key] = value;
  }
  found.STAGECRAFT_GENE_SETS = "off";
  found.STAGECRAFT_RUN_STATE = statePath;
  found.STAGECRAFT_FORMAL_PYTHON = python;
  found.STAGECRAFT_FORMAL_SCRIPTS = formalScripts;
  return found;
}

export default defineConfig({
  testDir: "e2e",
  outputDir: path.join(os.tmpdir(), "stagecraft-studio-e2e-output"),
  timeout: 30_000,
  workers: 1,
  use: { baseURL: "http://127.0.0.1:8771" },
  webServer: {
    command: `"${python}" -m stagecraft_studio.engine.cli serve --port 8771 --python "${python}" --script "${script}"`,
    cwd: root,
    url: "http://127.0.0.1:8771/",
    reuseExistingServer: false,
    timeout: 60_000,
    env: serverEnv(state),
  },
});
