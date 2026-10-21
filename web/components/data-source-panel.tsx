"use client";

/**
 * Executive Pulse — data source panel.
 *
 * Sample data, a published Google Sheet, an Excel/CSV file, or a REST
 * endpoint (CRM, project tool, BI export). Every source is mapped onto
 * the canonical schema by the same mapping layer, so unfamiliar column
 * names and status labels work without reformatting.
 *
 * Files are parsed in the browser — they are never uploaded.
 */

import { useEffect, useState } from "react";

import { useDashboard } from "@/components/dashboard-provider";
import { VALUE_COLUMNS, type ColumnMapping, type ValueMapping } from "@/lib/data/mapping";
import { REQUIRED_COLUMNS } from "@/lib/data/schema";
import { listSheets, parseXlsx, type SheetInfo } from "@/lib/data/xlsx";
import type { ScoredTask } from "@/lib/types";

interface MappingPreview {
  columns: string[];
  rows: number;
  suggestedColumns: ColumnMapping;
  unmapped: string[];
  unknownValues: Record<string, string[]>;
  suggestedValues: Record<string, Record<string, string>>;
}

type Panel = "sample" | "sheet" | "file";

export function DataSourcePanel() {
  const { source, setSource, refresh, needsMapping, setLocalDataset } = useDashboard();
  const [panel, setPanel] = useState<Panel>("sample");
  const [preview, setPreview] = useState<MappingPreview | null>(null);
  const [columns, setColumns] = useState<ColumnMapping>({});
  const [values, setValues] = useState<ValueMapping>({});
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [sheets, setSheets] = useState<SheetInfo[]>([]);
  const [sheetName, setSheetName] = useState<string | undefined>(undefined);

  // Ask the API for a mapping preview whenever the uploaded content changes.
  useEffect(() => {
    if (source.kind !== "upload" || (!source.csv && !source.xlsx)) {
      setPreview(null);
      return;
    }
    let cancelled = false;

    async function loadPreview() {
      setBusy(true);
      setError(null);
      try {
        const response = await fetch("/api/v1/mapping", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            csv: source.csv ?? "",
            table: source.xlsx ?? null,
            action: "preview",
          }),
        });
        const payload = await response.json();
        if (cancelled) return;
        if (!payload.ok) {
          setError(payload.error?.message ?? "Could not read the file");
          return;
        }
        setPreview(payload.data as MappingPreview);
        setColumns(payload.data.suggestedColumns as ColumnMapping);
        setValues(payload.data.suggestedValues as ValueMapping);
      } catch (caught) {
        if (!cancelled) {
          setError(caught instanceof Error ? caught.message : "Could not read the file");
        }
      } finally {
        if (!cancelled) setBusy(false);
      }
    }

    void loadPreview();
    return () => {
      cancelled = true;
    };
  }, [source.kind, source.csv, source.xlsx]);

  async function handleFile(file: File) {
    setError(null);
    setPreview(null);

    const isWorkbook = /\.xlsx$/i.test(file.name);
    if (isWorkbook) {
      try {
        setBusy(true);
        const listed = await listSheets(file);
        setSheets(listed);
        const table = await parseXlsx(file, listed[0]?.name);
        setSource({
          kind: "upload",
          fileName: file.name,
          xlsx: table,
          csv: "",
        });
      } catch (caught) {
        setError(
          caught instanceof Error ? caught.message : "Could not read the workbook",
        );
      } finally {
        setBusy(false);
      }
      return;
    }

    const text = await file.text();
    setSource({ kind: "upload", fileName: file.name, csv: text, xlsx: undefined });
  }

  const missing = Object.entries(columns)
    .filter(
      ([schemaCol, uploaded]) =>
        (REQUIRED_COLUMNS as readonly string[]).includes(schemaCol) && !uploaded,
    )
    .map(([schemaCol]) => schemaCol);

  const button = (
    id: Panel,
    label: string,
    active: boolean,
  ) => (
    <button
      type="button"
      className="ep-button"
      data-variant={active ? undefined : "secondary"}
      onClick={() => {
        setPanel(id);
        setError(null);
      }}
    >
      {label}
    </button>
  );

  return (
    <div>
      <div className="ep-sidebar-label">Data source</div>

      <div style={{ display: "flex", flexDirection: "column", gap: "0.35rem" }}>
        {button("sample", "Sample data", panel === "sample")}
        {button("sheet", "Google Sheet", panel === "sheet")}
        {button("file", "Excel / CSV", panel === "file")}
      </div>

      {panel === "sample" ? (
        <div
          className="dw-muted"
          style={{ marginTop: "0.6rem", fontSize: "0.6875rem" }}
        >
          A realistic dataset regenerated daily, so it always reflects a live
          operating picture.
        </div>
      ) : null}

      {panel === "sheet" ? (
        <div style={{ marginTop: "0.7rem" }}>
          <label className="ep-label" htmlFor="sheet-id">
            Sheet ID
          </label>
          <input
            id="sheet-id"
            className="ep-input"
            placeholder="1BxiMVs0XRA5nFMd…"
            value={source.sheetId ?? ""}
            onChange={(event) => setSource({ sheetId: event.target.value })}
          />
          <div
            className="dw-muted"
            style={{ marginTop: "0.35rem", fontSize: "0.6875rem" }}
          >
            Share as &ldquo;Anyone with the link&rdquo; or publish to the web
            as CSV. Paste the ID only, not the full URL.
          </div>
          <button
            type="button"
            className="ep-button"
            style={{ marginTop: "0.5rem", width: "100%" }}
            onClick={() => {
              setSource({ kind: "sheet" });
              refresh();
            }}
          >
            Load sheet
          </button>
        </div>
      ) : null}

      {panel === "file" ? (
        <div style={{ marginTop: "0.7rem" }}>
          <label
            className="ep-button"
            data-variant={source.kind === "upload" ? undefined : "secondary"}
            style={{ cursor: "pointer" }}
          >
            {source.kind === "upload" && source.fileName
              ? source.fileName
              : "Choose file"}
            <input
              type="file"
              accept=".csv,.xlsx,.txt"
              className="ep-input"
              style={{ display: "none" }}
              onChange={(event) => {
                const file = event.target.files?.[0];
                if (file) void handleFile(file);
              }}
            />
          </label>
          <div
            className="dw-muted"
            style={{ marginTop: "0.35rem", fontSize: "0.6875rem" }}
          >
            Parsed in your browser. The file is never uploaded.
          </div>
          {sheets.length > 1 ? (
            <>
              <label className="ep-label" htmlFor="sheet-name" style={{ marginTop: "0.6rem" }}>
                Sheet
              </label>
              <select
                id="sheet-name"
                className="ep-select"
                value={sheetName ?? sheets[0]?.name}
                onChange={async (event) => {
                  const chosen = event.target.value;
                  setSheetName(chosen);
                  const file = (event.target as HTMLSelectElement).closest(
                    "div",
                  )?.querySelector<HTMLInputElement>('input[type="file"]')?.files?.[0];
                  if (!file) return;
                  try {
                    const table = await parseXlsx(file, chosen);
                    setSource({ kind: "upload", fileName: file.name, xlsx: table, csv: "" });
                  } catch (caught) {
                    setError(caught instanceof Error ? caught.message : "Could not read the sheet");
                  }
                }}
              >
                {sheets.map((sheet) => (
                  <option key={sheet.name} value={sheet.name}>
                    {sheet.name} ({sheet.rows} rows)
                  </option>
                ))}
              </select>
            </>
          ) : null}
        </div>
      ) : null}


      {busy ? (
        <div className="dw-muted" style={{ marginTop: "0.6rem" }}>
          Reading…
        </div>
      ) : null}

      {error ? (
        <div
          className="dw-muted"
          style={{ marginTop: "0.6rem", color: "var(--color-critical)" }}
        >
          {error}
        </div>
      ) : null}

      {source.kind === "upload" && preview ? (
        <details className="ep-disclosure" style={{ marginTop: "0.7rem" }}>
          <summary>
            Map your data
            {missing.length > 0 ? ` · ${missing.length} left` : " · ready"}
          </summary>
          <div className="ep-disclosure-body">
            <div className="dw-muted" style={{ marginBottom: "0.6rem" }}>
              {preview.rows} rows detected. Match each field once — scores and
              ranking are never altered by mapping.
            </div>

            {REQUIRED_COLUMNS.map((schemaCol) => (
              <div key={schemaCol} style={{ marginBottom: "0.5rem" }}>
                <label className="ep-label" htmlFor={`map-${schemaCol}`}>
                  {schemaCol}
                </label>
                <select
                  id={`map-${schemaCol}`}
                  className="ep-select"
                  value={columns[schemaCol] ?? ""}
                  onChange={(event) =>
                    setColumns((current) => ({
                      ...current,
                      [schemaCol]: event.target.value || null,
                    }))
                  }
                >
                  <option value="">— select —</option>
                  {preview.columns.map((column) => (
                    <option key={column} value={column}>
                      {column}
                    </option>
                  ))}
                </select>
              </div>
            ))}

            {Object.entries(preview.unknownValues).map(([col, labels]) =>
              labels.map((label) => (
                <div key={`${col}-${label}`} style={{ marginBottom: "0.5rem" }}>
                  <label className="ep-label" htmlFor={`val-${col}-${label}`}>
                    {col}: &ldquo;{label}&rdquo; means
                  </label>
                  <select
                    id={`val-${col}-${label}`}
                    className="ep-select"
                    value={values[col]?.[label] ?? ""}
                    onChange={(event) =>
                      setValues((current) => ({
                        ...current,
                        [col]: {
                          ...(current[col] ?? {}),
                          [label]: event.target.value,
                        },
                      }))
                    }
                  >
                    <option value="">— select —</option>
                    {(VALUE_COLUMNS[col] ?? []).map((option) => (
                      <option key={option} value={option}>
                        {option}
                      </option>
                    ))}
                  </select>
                </div>
              )),
            )}

            <button
              type="button"
              className="ep-button"
              style={{ width: "100%", marginTop: "0.4rem" }}
              disabled={missing.length > 0}
              onClick={async () => {
                setBusy(true);
                setError(null);
                try {
                  const response = await fetch("/api/v1/mapping", {
                    method: "POST",
                    headers: { "Content-Type": "application/json" },
                    body: JSON.stringify({
                      csv: source.csv ?? "",
                      table: source.xlsx ?? null,
                      action: "apply",
                      columns,
                      values,
                    }),
                  });
                  const payload = await response.json();
                  if (!payload.ok) {
                    setError(payload.error?.message ?? "Mapping failed");
                    return;
                  }
                  // The mapped rows become the live dataset, scored in
                  // the browser. The file itself never leaves the page.
                  const scored = (payload.data?.tasks ?? []) as ScoredTask[];
                  const reference = payload.meta?.referenceDate
                    ? new Date(payload.meta.referenceDate).getTime()
                    : Date.now();
                  setLocalDataset(scored, reference);
                } catch (caught) {
                  setError(
                    caught instanceof Error ? caught.message : "Mapping failed",
                  );
                } finally {
                  setBusy(false);
                }
              }}
            >
              Apply mapping
            </button>
          </div>
        </details>
      ) : null}

      {needsMapping ? (
        <div
          className="dw-muted"
          style={{ marginTop: "0.6rem", color: "var(--color-warning)" }}
        >
          This source needs mapping before it can be scored.
        </div>
      ) : null}
    </div>
  );
}
