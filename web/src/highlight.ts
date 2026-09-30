import type { Highlighter } from "shiki";

let highlighter: Promise<Highlighter> | null = null;

export async function highlight(
  code: string,
  lang: "python" | "json",
): Promise<string> {
  highlighter ??= import("shiki").then((mod) =>
    mod.createHighlighter({
      themes: ["github-light"],
      langs: ["python", "json"],
    }),
  );
  const ready = await highlighter;
  return ready.codeToHtml(code, { lang, theme: "github-light" });
}
