import type { ProtocolValues } from "./panes/AssistantParts";

let pending: ProtocolValues | null = null;

export function queueProposal(values: ProtocolValues): void {
  pending = values;
  window.dispatchEvent(new Event("stagecraft:apply-proposal"));
}

export function hasProposal(): boolean {
  return pending !== null;
}

export function takeProposal(): ProtocolValues | null {
  const values = pending;
  pending = null;
  return values;
}
