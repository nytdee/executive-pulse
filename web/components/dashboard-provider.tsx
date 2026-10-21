"use client";

/**
 * Executive Pulse — dashboard context.
 *
 * One place that owns the active data source, the filters, the persona
 * lens and the focus profile. Every view reads from here, so the
 * sidebar, the pages and the API always agree.
 *
 * The dataset is fetched from the API rather than inlined by the
 * server, so all three sources (sample, Google Sheet, uploaded file)
 * travel the same path and there is no hydration mismatch.
 */

import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useRef,
  useState,
  type ReactNode,
} from "react";

import { extractProfileKeywords } from "@/lib/persona";
import { getCounts } from "@/lib/rule-engine";
import type { Counts, ScoredTask } from "@/lib/types";

export type SourceKind = "sample" | "sheet" | "upload";

export interface SourceState {
  kind: SourceKind;
  sheetId: string;
  gid: string;
  /** Raw CSV text for an uploaded file. */
  csv: string;
  /** Parsed workbook rows for an uploaded XLSX file. */
  xlsx: unknown;
  /** The uploaded file's display name. */
  fileName: string;
}

export interface Filters {
  departments: string[];
  owners: string[];
  statuses: string[];
  priorities: string[];
  search: string;
  minScore: number;
}

export const EMPTY_FILTERS: Filters = {
  departments: [],
  owners: [],
  statuses: [],
  priorities: [],
  search: "",
  minScore: 0,
};

interface DashboardContextValue {
  /** The full dataset, unscored filters applied. */
  tasks: ScoredTask[];
  /** The dataset after filters. */
  filtered: ScoredTask[];
  counts: Counts;
  filteredCounts: Counts;
  referenceMs: number;
  loading: boolean;
  error: string | null;
  source: SourceState;
  setSource: (source: Partial<SourceState>) => void;
  filters: Filters;
  setFilters: (filters: Partial<Filters>) => void;
  resetFilters: () => void;
  persona: string;
  setPersona: (persona: string) => void;
  focus: string;
  setFocus: (focus: string) => void;
  focusKeywords: string[];
  refresh: () => void;
  /** True when the active source still needs a mapping. */
  needsMapping: boolean;
  /** Publish a dataset scored in the browser. */
  setLocalDataset: (tasks: ScoredTask[], referenceMs: number) => void;
}

const DashboardContext = createContext<DashboardContextValue | null>(null);

export function useDashboard(): DashboardContextValue {
  const context = useContext(DashboardContext);
  if (!context) {
    throw new Error("useDashboard must be used inside <DashboardProvider>");
  }
  return context;
}

function buildQuery(source: SourceState, filters: Filters): string {
  const params = new URLSearchParams();

  if (source.kind === "sheet" && source.sheetId) {
    params.set("source", "sheet");
    params.set("sheetId", source.sheetId);
    params.set("gid", source.gid || "0");
  }

  if (filters.departments.length) {
    params.set("department", filters.departments.join(","));
  }
  if (filters.owners.length) params.set("owner", filters.owners.join(","));
  if (filters.statuses.length) params.set("status", filters.statuses.join(","));
  if (filters.priorities.length) {
    params.set("priority", filters.priorities.join(","));
  }
  if (filters.search.trim()) params.set("search", filters.search.trim());
  if (filters.minScore > 0) params.set("minScore", String(filters.minScore));

  return params.toString();
}

const VIEWER_STORAGE_KEY = "executive-pulse.viewer";

interface StoredViewer {
  persona: string;
  focus: string;
}

/**
 * Read the saved viewer (persona + focus) from this browser.
 * A CXO picks their lens once; it should survive navigation.
 */
function readStoredViewer(): StoredViewer {
  if (typeof window === "undefined") return { persona: "CEO", focus: "" };
  try {
    const raw = window.localStorage.getItem(VIEWER_STORAGE_KEY);
    if (!raw) return { persona: "CEO", focus: "" };
    const parsed = JSON.parse(raw) as Partial<StoredViewer>;
    return {
      persona: typeof parsed.persona === "string" ? parsed.persona : "CEO",
      focus: typeof parsed.focus === "string" ? parsed.focus : "",
    };
  } catch {
    return { persona: "CEO", focus: "" };
  }
}

function writeStoredViewer(viewer: StoredViewer): void {
  if (typeof window === "undefined") return;
  try {
    window.localStorage.setItem(VIEWER_STORAGE_KEY, JSON.stringify(viewer));
  } catch {
    // Private browsing or a full quota — persistence is a nicety.
  }
}

export function DashboardProvider({ children }: { children: ReactNode }) {
  const [source, setSourceState] = useState<SourceState>({
    kind: "sample",
    sheetId: "",
    gid: "0",
    csv: "",
    xlsx: null,
    fileName: "",
  });

  const [filters, setFiltersState] = useState<Filters>(EMPTY_FILTERS);
  const [persona, setPersonaState] = useState("CEO");
  const [focus, setFocusState] = useState("");

  // Refs keep the persistence callbacks free of stale closures.
  const personaRef = useRef("CEO");
  const focusRef = useRef("");

  const [tasks, setTasks] = useState<ScoredTask[]>([]);
  const [referenceMs, setReferenceMs] = useState<number>(0);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [needsMapping, setNeedsMapping] = useState(false);
  const [nonce, setNonce] = useState(0);
  /**
   * Datasets scored in the browser (uploaded files). When present, no
   * server fetch happens — the file never leaves the machine.
   */
  const [localTasks, setLocalTasks] = useState<ScoredTask[] | null>(null);
  const [localReferenceMs, setLocalReferenceMs] = useState<number>(0);

  const setSource = useCallback((next: Partial<SourceState>) => {
    setSourceState((current) => {
      const merged = { ...current, ...next };
      // Switching source invalidates any filter selection, and any
      // dataset that was scored locally.
      if (
        merged.kind !== current.kind ||
        merged.sheetId !== current.sheetId
      ) {
        setFiltersState(EMPTY_FILTERS);
        setLocalTasks(null);
      }
      return merged;
    });
  }, []);

  const setFilters = useCallback((next: Partial<Filters>) => {
    setFiltersState((current) => ({ ...current, ...next }));
  }, []);

  const setPersona = useCallback((next: string) => {
    personaRef.current = next;
    setPersonaState(next);
    writeStoredViewer({ persona: next, focus: focusRef.current });
  }, []);

  const setFocus = useCallback((next: string) => {
    focusRef.current = next;
    setFocusState(next);
    writeStoredViewer({ persona: personaRef.current, focus: next });
  }, []);

  // Restore the saved viewer on first load.
  useEffect(() => {
    const stored = readStoredViewer();
    personaRef.current = stored.persona;
    focusRef.current = stored.focus;
    setPersonaState(stored.persona);
    setFocusState(stored.focus);
  }, []);

  const resetFilters = useCallback(() => {
    setFiltersState(EMPTY_FILTERS);
  }, []);

  const refresh = useCallback(() => {
    setNonce((value) => value + 1);
  }, []);

  /**
   * Publish a dataset that was scored in the browser. Used by the
   * mapping flow so an uploaded file is never sent to the server.
   */
  const setLocalDataset = useCallback(
    (scored: ScoredTask[], reference: number) => {
      setLocalTasks(scored);
      setLocalReferenceMs(reference);
      setNeedsMapping(false);
      setError(null);
    },
    [],
  );

  useEffect(() => {
    // A locally scored dataset wins — no network round trip.
    if (localTasks) {
      setTasks(localTasks);
      setReferenceMs(localReferenceMs);
      setLoading(false);
      return;
    }

    let cancelled = false;
    const controller = new AbortController();

    async function load() {
      setLoading(true);
      setError(null);

      try {
        // POST keeps credentials and large payloads out of the URL.
        const response = await fetch("/api/v1/tasks", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          signal: controller.signal,
          body: JSON.stringify({
            source: {
              kind: source.kind,
              sheetId: source.sheetId || undefined,
              gid: source.gid || undefined,
            },
            filters,
          }),
        });
        const payload = await response.json();

        if (cancelled) return;

        if (!payload.ok) {
          if (payload.error?.code === "mapping_required") {
            setNeedsMapping(true);
            setTasks([]);
          } else {
            setError(payload.error?.message ?? "Failed to load data");
          }
          return;
        }

        setNeedsMapping(false);
        setTasks(payload.data.tasks as ScoredTask[]);
        setReferenceMs(new Date(payload.meta.referenceDate).getTime());
      } catch (caught) {
        if (!cancelled && (caught as Error).name !== "AbortError") {
          setError(
            caught instanceof Error ? caught.message : "Failed to load data",
          );
        }
      } finally {
        if (!cancelled) setLoading(false);
      }
    }

    void load();
    return () => {
      cancelled = true;
      controller.abort();
    };
  }, [source, filters, nonce, localTasks, localReferenceMs]);

  const counts = useMemo(() => getCounts(tasks), [tasks]);
  const focusKeywords = useMemo(
    () => (focus.trim() ? extractProfileKeywords(focus) : []),
    [focus],
  );

  const value: DashboardContextValue = {
    tasks,
    filtered: tasks,
    counts,
    filteredCounts: counts,
    referenceMs,
    loading,
    error,
    source,
    setSource,
    filters,
    setFilters,
    resetFilters,
    persona,
    setPersona,
    focus,
    setFocus,
    focusKeywords,
    refresh,
    needsMapping,
    setLocalDataset,
  };

  return (
    <DashboardContext.Provider value={value}>{children}</DashboardContext.Provider>
  );
}
