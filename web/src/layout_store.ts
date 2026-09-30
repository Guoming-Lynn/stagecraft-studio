const KEY = "stagecraft.layout";

export function readLayout(): Record<string, number> | undefined {
  if (typeof localStorage === "undefined") return undefined;
  const raw = localStorage.getItem(KEY);
  if (!raw) return undefined;
  try {
    return onlyNumbers(JSON.parse(raw) as unknown);
  } catch {
    return undefined;
  }
}

export function saveLayout(layout: Record<string, number>): void {
  const kept = onlyNumbers(layout);
  if (!kept) return;
  localStorage.setItem(KEY, JSON.stringify(kept));
}

function onlyNumbers(value: unknown): Record<string, number> | undefined {
  if (typeof value !== "object" || value === null) return undefined;
  const kept: Record<string, number> = {};
  for (const [key, item] of Object.entries(value)) {
    if (typeof item === "number") kept[key] = item;
  }
  return Object.keys(kept).length > 0 ? kept : undefined;
}
