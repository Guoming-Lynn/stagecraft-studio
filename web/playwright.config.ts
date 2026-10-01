import fs from "node:fs";
import os from "node:os";
import path from "node:path";
import { fileURLToPath } from "node:url";

import { defineConfig } from "@playwright/test";

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");
const engine = path.join(os.tmpdir(), "stagecraft-studio-e2e");
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
fs.writeFileSync(path.join(engine, "write_demo_h5ad.py"), DEMO_WRITER, "utf8");
fs.writeFileSync(script, PIPELINE, "utf8");

function serverEnv(statePath: string): Record<string, string> {
  const found: Record<string, string> = {};
  for (const [key, value] of Object.entries(process.env)) {
    if (value !== undefined) found[key] = value;
  }
  found.STAGECRAFT_GENE_SETS = "off";
  found.STAGECRAFT_RUN_STATE = statePath;
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
