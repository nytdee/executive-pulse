/**
 * Change-detection baseline store.
 *
 * Serverless platforms have an ephemeral filesystem, so the previous
 * snapshot of the data cannot live on disk. This module keeps the
 * baseline in memory for the lifetime of the server instance and
 * exposes a hook (`setSnapshotBackend`) so a durable backend can be
 * plugged in — a Redis/KV store, a database, or an object store.
 *
 * The semantics match the Python reference: the baseline only advances
 * when the data actually changed, so the change feed stays visible
 * until a new change occurs.
 */

export interface BaselineTask {
  Task_ID: string;
  Status: string;
  Due_Date: string;
  Last_Updated: string;
  Executive_Decision_Required: boolean;
  Blocker: string;
  overdue: boolean;
  blocked: boolean;
  decision_required: boolean;
}
export interface Baseline {
  fingerprint: string;
  savedAt: string;
  tasks: BaselineTask[];
}
export interface SnapshotBackend {
  get(key: string): Promise<Baseline | null>;
  set(key: string, baseline: Baseline): Promise<void>;
}

/**
 * In-memory backend. Works for a single server instance and for local
 * development. Replace with a durable backend for multi-instance or
 * long-lived deployments.
 */
class MemoryBackend implements SnapshotBackend {
  private store = new Map<string, Baseline>();

  async get(key: string): Promise<Baseline | null> {
    return this.store.get(key) ?? null;
  }

  async set(key: string, baseline: Baseline): Promise<void> {
    this.store.set(key, baseline);
  }
}

/**
 * Redis / Vercel KV backend, over the REST API.
 *
 * No extra dependency: Upstash and Vercel KV both expose a REST API,
 * so this works with either. Configure with the two environment
 * variables below.
 *
 *   KV_REST_API_URL   e.g. https://xxx.upstash.io
 *   KV_REST_API_TOKEN the REST token
 *
 * Install it once at startup:
 *
 *   import { setSnapshotBackend } from "@/lib/snapshot-store";
 *   setSnapshotBackend(new RedisSnapshotBackend({
 *     url: process.env.KV_REST_API_URL!,
 *     token: process.env.KV_REST_API_TOKEN!,
 *   }));
 */
export class RedisSnapshotBackend implements SnapshotBackend {
  constructor(
    private readonly config: { url: string; token: string; prefix?: string },
  ) {}

  private key(name: string): string {
    return `${this.config.prefix ?? "executive-pulse:snapshot:"}${name}`;
  }

  async get(key: string): Promise<Baseline | null> {
    const response = await fetch(`${this.config.url}/get/${this.key(key)}`, {
      headers: { Authorization: `Bearer ${this.config.token}` },
    });
    if (!response.ok) return null;
    const payload = (await response.json()) as { result?: string | null };
    if (!payload.result) return null;
    try {
      return JSON.parse(payload.result) as Baseline;
    } catch {
      return null;
    }
  }

  async set(key: string, baseline: Baseline): Promise<void> {
    // 30 days is long enough to cover a review cycle.
    await fetch(`${this.config.url}/set/${this.key(key)}`, {
      method: "POST",
      headers: {
        Authorization: `Bearer ${this.config.token}`,
        "Content-Type": "application/json",
      },
      body: JSON.stringify(JSON.stringify(baseline)),
    });
  }
}

let backend: SnapshotBackend = new MemoryBackend();

/** Swap in a durable backend (KV, Redis, database). */
export function setSnapshotBackend(next: SnapshotBackend): void {
  backend = next;
}

/**
 * Install the durable backend when its environment variables are present.
 * Call this once, at module load, in the app's server entry point.
 */
export function installDurableSnapshotBackend(): void {
  const url = process.env.KV_REST_API_URL;
  const token = process.env.KV_REST_API_TOKEN;
  if (url && token) {
    backend = new RedisSnapshotBackend({ url, token });
  }
}

/** Load the stored baseline for a data source. */
export async function loadBaseline(key: string): Promise<Baseline | null> {
  try {
    return await backend.get(key);
  } catch {
    return null;
  }
}

/** Persist a new baseline for a data source. */
export async function saveBaseline(
  key: string,
  baseline: Baseline,
): Promise<void> {
  try {
    await backend.set(key, baseline);
  } catch {
    // A failure to store the baseline must not break the response.
  }
}
