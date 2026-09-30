import { useVirtualizer } from "@tanstack/react-virtual";
import {
  getCoreRowModel,
  useLegacyTable,
  type LegacyColumnDef,
} from "@tanstack/react-table/legacy";
import { flexRender } from "@tanstack/react-table";
import { useEffect, useMemo, useRef, useState } from "react";

import { errorText, loadTable, type TablePage } from "../api/client";
import { chrome, rowCount } from "../text/chrome";

type GridRow = string[];

export function CsvView({ runId, rel }: { runId: string; rel: string }) {
  const parentRef = useRef<HTMLDivElement>(null);
  const cache = useRef(new Map<number, GridRow>());
  const [query, setQuery] = useState("");
  const [needle, setNeedle] = useState("");
  const [sort, setSort] = useState("");
  const [desc, setDesc] = useState(false);
  const [names, setNames] = useState<string[]>([]);
  const [total, setTotal] = useState(0);
  const [message, setMessage] = useState("");
  const [stamp, setStamp] = useState(0);
  const requestKey = useRef("");

  useEffect(() => {
    const timer = window.setTimeout(() => setNeedle(query.trim()), 250);
    return () => window.clearTimeout(timer);
  }, [query]);

  useEffect(() => {
    cache.current = new Map();
    requestKey.current = "";
    setTotal(0);
    setStamp((value) => value + 1);
  }, [needle, sort, desc, rel, runId]);

  const virtualizer = useVirtualizer({
    count: Math.max(total, 1),
    getScrollElement: () => parentRef.current,
    estimateSize: () => 28,
    overscan: 8,
  });
  const start = virtualizer.getVirtualItems()[0]?.index ?? 0;

  useEffect(() => {
    if (total > 0 && start >= total) return;
    const end = total > 0 ? Math.min(start + 40, total) : start + 40;
    let hole = start;
    while (hole < end && cache.current.has(hole)) hole += 1;
    if (hole >= end) return;
    const key = `${needle}|${sort}|${desc}|${rel}|${hole}`;
    if (requestKey.current === key) return;
    requestKey.current = key;
    let stop = false;
    void loadTable(runId, rel, {
      offset: hole,
      limit: 100,
      q: needle,
      sort,
      desc,
    })
      .then((page) => {
        if (stop) return;
        remember(cache.current, page, hole);
        setNames(page.columns);
        setTotal(page.total);
        setMessage("");
        setStamp((value) => value + 1);
      })
      .catch((reason: unknown) => setMessage(errorText(reason)));
    return () => {
      stop = true;
      requestKey.current = "";
    };
  }, [start, stamp, total, needle, sort, desc, rel, runId]);

  const columns = useMemo<LegacyColumnDef<GridRow>[]>(
    () =>
      names.map((name, index) => ({
        id: name,
        header: name,
        accessorFn: (row) => row[index] ?? "",
      })),
    [names],
  );
  const visible = virtualizer
    .getVirtualItems()
    .map((item) => cache.current.get(item.index) ?? names.map(() => ""));
  const table = useLegacyTable({
    data: visible,
    columns,
    manualSorting: true,
    state: { sorting: sort ? [{ id: sort, desc }] : [] },
    onSortingChange: (updater) => {
      const current = sort ? [{ id: sort, desc }] : [];
      const next = typeof updater === "function" ? updater(current) : updater;
      setSort(next[0]?.id ?? "");
      setDesc(Boolean(next[0]?.desc));
    },
    getCoreRowModel: getCoreRowModel(),
  });

  return (
    <div className="csv">
      <div className="csv-toolbar">
        <label>
          {chrome.searchGene}
          <input
            placeholder={chrome.searchPlaceholder}
            value={query}
            onChange={(event) => setQuery(event.target.value)}
          />
        </label>
        {total > 0 ? (
          <span className="csv-count">{rowCount(total)}</span>
        ) : null}
      </div>
      {message ? <p className="log-error">{message}</p> : null}
      <div className="csv-head">
        {table.getHeaderGroups().map((group) =>
          group.headers.map((header) => (
            <button
              key={header.id}
              type="button"
              onClick={header.column.getToggleSortingHandler()}
            >
              {flexRender(header.column.columnDef.header, header.getContext())}
              {header.column.getIsSorted() === "asc" ? " ↑" : ""}
              {header.column.getIsSorted() === "desc" ? " ↓" : ""}
            </button>
          )),
        )}
      </div>
      <div className="csv-body" ref={parentRef}>
        <div style={{ height: virtualizer.getTotalSize() }}>
          {virtualizer.getVirtualItems().map((item) => (
            <div
              key={item.key}
              className="csv-row"
              style={{ transform: `translateY(${item.start}px)` }}
            >
              {(cache.current.get(item.index) ?? []).map((cell, index) => (
                <span key={`${item.index}-${index}`}>{cell}</span>
              ))}
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}

function remember(
  cache: Map<number, GridRow>,
  page: TablePage,
  hole: number,
): void {
  page.rows.forEach((row, index) => cache.set(hole + index, row));
}
