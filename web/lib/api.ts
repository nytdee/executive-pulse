/**
 * Shared API helpers.
 *
 * Every endpoint returns the same envelope so consumers can rely on the
 * shape: { ok, data, meta } on success and { ok: false, error } on
 * failure. Caching is explicit and short — operational data changes.
 */

import { NextResponse } from "next/server";

export interface ApiMeta {
  /** ISO timestamp of when the response was produced. */
  generatedAt: string;
  /** Which data source produced it. */
  source: string;
  /** Total rows before filtering. */
  total: number;
  /** Rows after filtering. */
  filtered: number;
  /** Human-readable reference date used by the engine. */
  referenceDate: string;
  /** Any non-fatal warnings, e.g. a mapping that needed a fallback. */
  warnings?: string[];
}

export interface ApiEnvelope<T> {
  ok: true;
  data: T;
  meta: ApiMeta;
}

export interface ApiError {
  ok: false;
  error: {
    code: string;
    message: string;
    details?: unknown;
  };
}

export function ok<T>(
  data: T,
  meta: Omit<ApiMeta, "generatedAt">,
  init?: ResponseInit,
): NextResponse<ApiEnvelope<T>> {
  return NextResponse.json(
    {
      ok: true,
      data,
      meta: { ...meta, generatedAt: new Date().toISOString() },
    },
    init,
  );
}

export function fail(
  code: string,
  message: string,
  status = 400,
  details?: unknown,
): NextResponse<ApiError> {
  return NextResponse.json(
    { ok: false, error: { code, message, details } },
    { status },
  );
}

/** Read the shared query parameters every endpoint understands. */
export function readParams(request: Request) {
  const url = new URL(request.url);
  return {
    url,
    params: url.searchParams,
    source: url.searchParams.get("source") ?? "sample",
    sheetId: url.searchParams.get("sheetId") ?? "",
    gid: url.searchParams.get("gid") ?? "0",
    persona: url.searchParams.get("persona"),
    focus: url.searchParams.get("focus"),
  };
}
