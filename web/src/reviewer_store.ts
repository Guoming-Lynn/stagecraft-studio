const REVIEWER_KEY = "stagecraft_reviewer";

export function readReviewer(): string {
  if (typeof window === "undefined") return "";
  return window.localStorage.getItem(REVIEWER_KEY) ?? "";
}

export function saveReviewer(value: string): void {
  if (typeof window === "undefined") return;
  const trimmed = value.trim();
  if (trimmed) {
    window.localStorage.setItem(REVIEWER_KEY, trimmed);
  } else {
    window.localStorage.removeItem(REVIEWER_KEY);
  }
}

export function todayIso(): string {
  return new Date().toISOString().slice(0, 10);
}
