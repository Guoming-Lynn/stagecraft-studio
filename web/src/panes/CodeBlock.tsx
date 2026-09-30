import { useEffect, useState } from "react";

import { highlight } from "../highlight";

export function CodeBlock({
  code,
  lang,
}: {
  code: string;
  lang: "python" | "json";
}) {
  const [html, setHtml] = useState("");
  useEffect(() => {
    let stop = false;
    void highlight(code, lang).then((next) => {
      if (!stop) setHtml(next);
    });
    return () => {
      stop = true;
    };
  }, [code, lang]);
  if (!html) return <pre>{code}</pre>;
  return (
    <div className="highlighted" dangerouslySetInnerHTML={{ __html: html }} />
  );
}
