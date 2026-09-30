import type { components } from "./schema";

export type Bootstrap = components["schemas"]["Bootstrap"];
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
