/**
 * Executive Pulse — identity and viewer scope.
 *
 * The product answers different questions depending on who is looking:
 *
 *   - "What needs my attention?"  — scoped to the viewer's department
 *   - "Where is my input required?" — decisions waiting on them
 *   - "What is happening across the org?" — the whole picture
 *
 * Today the viewer is chosen from a selector, which is right for a
 * public demo and for a pilot where people share a link. When this is
 * deployed inside a company, the same interface is satisfied by the
 * signed-in user instead — see `resolveViewer`.
 *
 * Nothing in the engine depends on identity. The viewer only scopes
 * which rows are shown; it never changes a score.
 */

import { PERSONAS, personaDepartments } from "./persona";

export interface Viewer {
  /** Display name, e.g. "Deepanshu" or "Priya Legal". */
  name: string;
  /**
   * The persona lens, which maps to a set of departments.
   * "CEO" and "Chief of Staff" see the whole organization.
   */
  persona: string;
  /** Departments the viewer owns. Empty means the whole organization. */
  departments: string[];
  /** Freeform focus terms, e.g. ["design", "partnerships"]. */
  focus: string[];
  /** Where this came from: a selector, or a real identity provider. */
  origin: "selector" | "session";
}

/** The personas a viewer can adopt, with their department scope. */
export interface PersonaOption {
  id: string;
  label: string;
  departments: string[];
  description: string;
}

export const PERSONA_OPTIONS: PersonaOption[] = [
  {
    id: "CEO",
    label: "CEO",
    departments: [],
    description: "The whole organization",
  },
  {
    id: "Chief of Staff",
    label: "Chief of Staff",
    departments: [],
    description: "The whole organization, cross-functional",
  },
  {
    id: "CMO",
    label: "CMO",
    departments: personaDepartments("CMO") ?? [],
    description: "Marketing and Sales",
  },
  {
    id: "CFO",
    label: "CFO",
    departments: personaDepartments("CFO") ?? [],
    description: "Finance and Legal",
  },
  {
    id: "CTO / CPO",
    label: "CTO / CPO",
    departments: personaDepartments("CTO / CPO") ?? [],
    description: "Technology and Product",
  },
  {
    id: "COO",
    label: "COO",
    departments: personaDepartments("COO") ?? [],
    description: "Operations, Technology and People",
  },
];

/** Build a viewer from the current selector state. */
export function viewerFromSelector(
  persona: string,
  focus: string[],
  name = "Executive",
): Viewer {
  return {
    name,
    persona,
    departments: personaDepartments(persona) ?? [],
    focus,
    origin: "selector",
  };
}

/**
 * Resolve the viewer for a request.
 *
 * In demo mode this reads the selector. In a deployed instance a real
 * session would be resolved here — the signature is already shaped for
 * it, so swapping the implementation does not touch the engine or UI.
 *
 * To plug in a real identity provider, implement `SessionResolver` and
 * pass it to `setSessionResolver`.
 */
export interface SessionResolver {
  /** Resolve the viewer for a request, or null when there is no session. */
  resolve(request: Request): Promise<Viewer | null>;
}

let sessionResolver: SessionResolver | null = null;

/** Install a real identity resolver. */
export function setSessionResolver(resolver: SessionResolver | null): void {
  sessionResolver = resolver;
}

/** Resolve the viewer, falling back to the selector in demo mode. */
export async function resolveViewer(
  request: Request,
  fallback: Viewer,
): Promise<Viewer> {
  if (!sessionResolver) return fallback;
  try {
    const resolved = await sessionResolver.resolve(request);
    return resolved ?? fallback;
  } catch {
    return fallback;
  }
}

/**
 * Does this viewer own this row?
 *
 * Used to scope "my input required" and the "for you" grouping.
 */
export function viewerOwnsRow(
  viewer: Viewer,
  row: { Department?: string },
): boolean {
  if (viewer.focus.length > 0) {
    // A focus profile is the most specific statement of ownership, and
    // it is checked by the caller (which has the full row).
    return true;
  }
  if (viewer.departments.length === 0) return true;
  return viewer.departments.includes(row.Department ?? "");
}
