import type { components } from "./schema";

export type Bootstrap = components["schemas"]["Bootstrap"];
export type CompareView = components["schemas"]["CompareView"];
export type InspectView = components["schemas"]["InspectView"];
export type QuicklookForm = components["schemas"]["QuicklookForm"];
export type RevealResult = components["schemas"]["RevealResult"];
export type RunListItem = components["schemas"]["RunListItem"];
export type RunView = components["schemas"]["RunView"];
export type SourceView = components["schemas"]["SourceView"];
export type Started = components["schemas"]["Started"];
export type StepView = components["schemas"]["StepView"];
export type TreeEntry = components["schemas"]["TreeEntry"];
export type TablePage = components["schemas"]["TablePage"];
export type FilePreview = components["schemas"]["FilePreview"];
export type EnvironmentReport = components["schemas"]["EnvironmentReport"];
export type DemoStarted = components["schemas"]["DemoStarted"];

let token = "";

export function rememberToken(value: string): void {
  token = value;
}

export function mediaUrl(runId: string, rel: string): string {
  return `/api/runs/${runId}/media?rel=${encodeURIComponent(rel)}`;
}

export function loadBootstrap(): Promise<Bootstrap> {
  return send("/api/bootstrap");
}

export function loadRuns(): Promise<RunListItem[]> {
  return send("/api/runs");
}

export function loadRun(runId: string): Promise<RunView> {
  return send(`/api/runs/${runId}`);
}

export function loadSteps(runId: string): Promise<StepView[]> {
  return send(`/api/runs/${runId}/steps`);
}

export function loadTree(runId: string): Promise<TreeEntry[]> {
  return send(`/api/runs/${runId}/tree`);
}

export function loadFile(runId: string, rel: string): Promise<FilePreview> {
  const params = new URLSearchParams({ rel });
  return send(`/api/runs/${runId}/file?${params}`);
}

export function loadTable(
  runId: string,
  rel: string,
  query: {
    offset: number;
    limit: number;
    q: string;
    sort: string;
    desc: boolean;
  },
): Promise<TablePage> {
  const params = new URLSearchParams({
    rel,
    offset: String(query.offset),
    limit: String(query.limit),
    q: query.q,
    sort: query.sort,
    desc: String(query.desc),
  });
  return send(`/api/runs/${runId}/table?${params}`);
}

export function bundleUrl(runId: string): string {
  return `/api/runs/${runId}/bundle`;
}

export function loadCompare(left: string, right: string): Promise<CompareView> {
  const params = new URLSearchParams({ left, right });
  return send(`/api/compare?${params}`);
}

export function loadEnvironment(): Promise<EnvironmentReport> {
  return send("/api/environment");
}

export function startDemo(): Promise<DemoStarted> {
  return send("/api/demo", { method: "POST", body: "{}" });
}

export function loadSource(stepId: string): Promise<SourceView> {
  return send(`/api/steps/${stepId}/source`);
}

export function startRun(form: QuicklookForm): Promise<Started> {
  return send("/api/runs", { method: "POST", body: JSON.stringify(form) });
}

export function inspectInput(form: QuicklookForm): Promise<InspectView> {
  return send("/api/inspect", { method: "POST", body: JSON.stringify(form) });
}

export function cancelRun(runId: string): Promise<RunView> {
  return send(`/api/runs/${runId}/cancel`, { method: "POST", body: "{}" });
}

export function revealRun(runId: string): Promise<RevealResult> {
  return send(`/api/runs/${runId}/reveal`, { method: "POST", body: "{}" });
}

export type StageRunItem = { id: number; stage_status: string };
export type ResolutionTile = {
  resolution: string;
  n_clusters: number;
  min_cluster_size: number;
  max_cluster_size: number;
};
export type ReviewCenter = {
  id: number;
  stage_status: string;
  quicklook_seen: boolean;
  evidence_hash: string;
  resolutions: ResolutionTile[];
  clusters: string[];
  genes: { gene: string; expression: number[] }[];
  scientific_status: {
    scientific_status: string;
    calibration_status: string;
    associated: boolean;
    claims_limma: boolean;
    forecast_is_not_a_verdict: boolean;
    lodo_is_replication: boolean;
    holdout: string;
    read_only: boolean;
    limits: string[];
  };
};

export function loadStageRuns(): Promise<StageRunItem[]> {
  return send("/api/stage-runs");
}

export function loadReviewCenter(runId: number): Promise<ReviewCenter> {
  return send(`/api/stage-runs/${runId}/center`);
}

export type ProtocolField = {
  name: string;
  kind: string;
  reason: string;
  freeze_impact: string;
  default?: unknown;
  forbidden?: string[];
};

export function loadProtocolForm(): Promise<{ fields: ProtocolField[] }> {
  return send("/api/protocol/form");
}

export function freezeProtocol(body: {
  target_gene: string;
  species: string;
  harmony_keys: string[];
  loose_min_genes: number;
  data_path: string;
  libraries: { library_id: string; dataset: string }[];
}): Promise<{ content_hash: string; stage_run_id: number }> {
  return send("/api/protocol/freeze", {
    method: "POST",
    body: JSON.stringify(body),
  });
}

export function submitResolution(
  runId: number,
  body: Record<string, string>,
): Promise<unknown> {
  return send(`/api/stage-runs/${runId}/resolution`, {
    method: "POST",
    body: JSON.stringify(body),
  });
}

export function submitClusters(
  runId: number,
  body: { blinding: string; rows: Record<string, string>[] },
): Promise<unknown> {
  return send(`/api/stage-runs/${runId}/clusters`, {
    method: "POST",
    body: JSON.stringify(body),
  });
}

export interface Part3CenterView {
  stage_run_id: number;
  target_gene: string;
  resolutions: {
    resolution: string;
    n_clusters: number;
    min_cluster_size: number;
    max_cluster_size: number;
  }[];
  clusters: string[];
  evidence_hash: string;
  active_stop_point:
    | "AWAITING_RECLUSTER"
    | "STOP1_RESOLUTION"
    | "STOP2_CLUSTERS"
    | "CLEANUP_REQUIRED"
    | "STOP3_NAMES"
    | "COMPLETED";
  quicklook_seen: boolean;
  current_resolution: {
    resolution: string;
    reviewer: string;
    decided_on: string;
    rationale: string;
    blinding: string;
    leiden_ids: string[];
  } | null;
  current_clusters: {
    rows: {
      cluster: string;
      decision: "KEEP" | "DELETE";
      rationale: string;
      reviewer: string;
      decided_on: string;
    }[];
    blinding: string;
  } | null;
  current_names: {
    rows: {
      cluster: string;
      name: string;
      rationale: string;
      reviewer: string;
      decided_on: string;
    }[];
    blinding: string;
  } | null;
}

export function loadPart3Center(runId: number): Promise<Part3CenterView> {
  return send(`/api/stage-runs/${runId}/part3/center`);
}

export function submitPart3Resolution(
  runId: number,
  body: {
    reviewer: string;
    decided_on: string;
    rationale: string;
    evidence_hash: string;
    resolution: string;
    blinding: string;
  },
): Promise<unknown> {
  return send(`/api/stage-runs/${runId}/part3/resolution`, {
    method: "POST",
    body: JSON.stringify(body),
  });
}

export function submitPart3Clusters(
  runId: number,
  body: {
    blinding: string;
    rows: {
      cluster: string;
      decision: string;
      rationale: string;
      reviewer: string;
      decided_on: string;
      name?: string;
    }[];
  },
): Promise<unknown> {
  return send(`/api/stage-runs/${runId}/part3/clusters`, {
    method: "POST",
    body: JSON.stringify(body),
  });
}

export function submitPart3Names(
  runId: number,
  body: {
    blinding: string;
    rows: {
      cluster: string;
      name: string;
      rationale: string;
      reviewer: string;
      decided_on: string;
    }[];
  },
): Promise<unknown> {
  return send(`/api/stage-runs/${runId}/part3/names`, {
    method: "POST",
    body: JSON.stringify(body),
  });
}

export interface StageWorkspaceView {
  id: number;
  stage_status: string;
  invalidated: boolean;
  inputs: {
    project_id: number | null;
    project_name: string;
    root_path: string;
    protocol_id: number | null;
    protocol_hash: string;
    input_hash: string;
    target_gene: string;
    species: string;
    data_path: string;
    document: Record<string, unknown>;
  };
  parameters: {
    job_id: number;
    task_id: string;
    job_status: string;
    fields: Record<string, unknown>;
  }[];
  results: {
    scientific_status: {
      scientific_status: string;
      calibration_status: string;
      associated: boolean;
      claims_limma: boolean;
      forecast_is_not_a_verdict: boolean;
      lodo_is_replication: boolean;
      holdout: string;
      read_only: boolean;
      limits: string[];
    };
    evidence: Record<string, unknown>;
    artifacts: {
      id: number;
      job_id: number;
      relative_path: string;
      content_hash: string;
      artifact_status: string;
    }[];
  };
  checks: {
    id: number;
    rule_id: string;
    rule_status: string;
    detail: Record<string, unknown>;
    checked_at: string | null;
  }[];
  logs: {
    id: number;
    task_id: string;
    job_status: string;
    failure_reason: string | null;
    created_at: string | null;
  }[];
}

export function loadStageWorkspace(runId: number): Promise<StageWorkspaceView> {
  return send(`/api/stage-runs/${runId}/workspace`);
}

export interface GalleryFigureItem {
  id: string;
  task_id: string;
  title: string;
  stage_part: string;
  panel_id: string;
  status: "AVAILABLE" | "NOT_ESTIMABLE" | "STOPPED";
  format_png: string | null;
  format_svg: string | null;
  format_pdf: string | null;
  source_data: string | null;
  parameters: string | null;
  caption: string;
  reasons: string[];
  content_hash: string;
}

export interface StageGalleryView {
  run_id: number;
  project_id: number;
  scientific_status: {
    calibration_status: string;
    associated: boolean;
    evidence_ceiling: string;
    reasons: string[];
  };
  figures: GalleryFigureItem[];
  total_figures: number;
  available_count: number;
  not_estimable_count: number;
}

export function loadStageGallery(runId: number): Promise<StageGalleryView> {
  return send(`/api/stage-runs/${runId}/gallery`);
}

export function stageArtifactUrl(runId: number, rel: string): string {
  return `/api/stage-runs/${runId}/artifacts/raw?rel=${encodeURIComponent(rel)}`;
}

export function errorText(error: unknown): string {
  if (!(error instanceof Error)) return "请求失败";
  try {
    const payload = JSON.parse(error.message) as unknown;
    if (
      typeof payload === "object" &&
      payload !== null &&
      "detail" in payload
    ) {
      const detail = payload.detail;
      if (typeof detail === "string") return detail;
      if (
        typeof detail === "object" &&
        detail !== null &&
        "rule_id" in detail
      ) {
        return String(detail.rule_id);
      }
    }
  } catch {
    return error.message;
  }
  return error.message;
}

async function send<T>(path: string, init?: RequestInit): Promise<T> {
  const headers = new Headers(init?.headers);
  if (init?.body !== undefined) {
    headers.set("Content-Type", "application/json");
    headers.set("X-Stagecraft-Token", token);
  }
  const response = await fetch(path, { ...init, headers });
  if (!response.ok) throw new Error(await response.text());
  return (await response.json()) as T;
}
