export function lineClass(line: string): string {
  if (line.includes("ERROR")) return "log-error";
  if (line.includes("WARNING")) return "log-warning";
  return "log-line";
}

export function shouldFollowLog(node: {
  scrollTop: number;
  scrollHeight: number;
  clientHeight: number;
}): boolean {
  return node.scrollHeight - node.scrollTop - node.clientHeight < 24;
}
