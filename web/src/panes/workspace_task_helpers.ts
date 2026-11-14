import type { StageWorkspaceView } from "../api/client";

export type ProtocolLibraryRow = {
  library_id: string;
  dataset: string;
  donor_id: string;
  source_block: string;
};

export function taskStatusClass(status: string): string {
  if (status === "COMPLETED") return "task-status task-status-ok";
  if (status === "RUNNING" || status === "QUEUED") {
    return "task-status task-status-active";
  }
  if (status === "FAILED" || status === "INTERRUPTED") {
    return "task-status task-status-bad";
  }
  return "task-status";
}

export function latestTaskStatus(
  ws: StageWorkspaceView,
  taskId: string,
  libraryId?: string,
): string {
  for (let i = ws.parameters.length - 1; i >= 0; i -= 1) {
    const job = ws.parameters[i];
    if (!job || job.task_id !== taskId) continue;
    if (libraryId && String(job.fields.library_id ?? "") !== libraryId) {
      continue;
    }
    return job.job_status;
  }
  return "";
}

export function extractProtocolLibraries(
  ws: StageWorkspaceView,
): ProtocolLibraryRow[] {
  const doc = ws.inputs.document;
  const raw = doc.manifest ?? doc.libraries;
  if (!Array.isArray(raw)) return [];
  const rows: ProtocolLibraryRow[] = [];
  for (const item of raw) {
    if (!item || typeof item !== "object") continue;
    const rec = item as Record<string, unknown>;
    const libId = String(rec.library_id ?? "").trim();
    if (!libId) continue;
    rows.push({
      library_id: libId,
      dataset: String(rec.dataset ?? ""),
      donor_id: String(rec.donor_id ?? ""),
      source_block: String(rec.source_block ?? ""),
    });
  }
  return rows;
}

export function extractLockedCellTypes(ws: StageWorkspaceView): string[] {
  const lock = ws.results.evidence.lock;
  if (!lock || typeof lock !== "object") return [];
  const mapping = (lock as Record<string, unknown>).mapping;
  if (!mapping || typeof mapping !== "object") return [];
  const seen = new Set<string>();
  for (const val of Object.values(mapping as Record<string, unknown>)) {
    const text = typeof val === "string" ? val.trim() : "";
    if (text) seen.add(text);
  }
  return [...seen];
}

export function hasActiveFormalJobs(ws: StageWorkspaceView | null): boolean {
  if (!ws) return false;
  return ws.parameters.some(
    (job) => job.job_status === "QUEUED" || job.job_status === "RUNNING",
  );
}
