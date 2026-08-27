import { Pool, type QueryResultRow } from "pg";

/**
 * Single shared Postgres pool.
 *
 * Vercel serverless re-uses warm lambdas, so we cache the pool on globalThis to
 * avoid opening a new connection on every invocation. Keep max low — serverless
 * fans out, and Postgres connection limits are the usual first thing to break.
 */
declare global {
  // eslint-disable-next-line no-var
  var __veraPool: Pool | undefined;
}

function createPool(): Pool {
  const connectionString = process.env.DATABASE_URL;
  if (!connectionString) {
    throw new Error(
      "DATABASE_URL is not set. Add it in Vercel → Settings → Environment Variables.",
    );
  }

  return new Pool({
    connectionString,
    max: 3,
    idleTimeoutMillis: 10_000,
    connectionTimeoutMillis: 10_000,
    // Managed Postgres (Neon, Supabase, Vercel) terminates TLS at the pooler.
    ssl: connectionString.includes("localhost")
      ? undefined
      : { rejectUnauthorized: false },
  });
}

export function pool(): Pool {
  if (!global.__veraPool) global.__veraPool = createPool();
  return global.__veraPool;
}

/** Run a query and return all rows. */
export async function sql<T extends QueryResultRow = QueryResultRow>(
  text: string,
  params: unknown[] = [],
): Promise<T[]> {
  const res = await pool().query<T>(text, params);
  return res.rows;
}

/** Run a query and return the first row, or null. */
export async function one<T extends QueryResultRow = QueryResultRow>(
  text: string,
  params: unknown[] = [],
): Promise<T | null> {
  const rows = await sql<T>(text, params);
  return rows[0] ?? null;
}

/** True when the schema has been applied. Used by the setup screen. */
export async function isInitialized(): Promise<boolean> {
  try {
    await sql("SELECT 1 FROM clients LIMIT 1");
    return true;
  } catch {
    return false;
  }
}

// ---------------------------------------------------------------------------
// Row types
// ---------------------------------------------------------------------------

export interface Client {
  id: string;
  slug: string;
  name: string;
  contact_name: string | null;
  contact_email: string | null;
  contact_phone: string | null;
  industry: string | null;
  city: string | null;
  state: string | null;
  website: string | null;
  status: "prospect" | "onboarding" | "active" | "paused" | "churned";
  monthly_value: string | null;
  started_at: string | null;
  stripe_customer_id: string | null;
  health_score: number;
  health_notes: string | null;
  last_reviewed_at: string | null;
  last_contact_at: string | null;
  notes: string | null;
  created_at: string;
  updated_at: string;
}

export interface Deliverable {
  id: string;
  client_id: string;
  title: string;
  kind: string;
  status: "planned" | "in_progress" | "delivered" | "blocked" | "cancelled";
  detail: string | null;
  url: string | null;
  due_at: string | null;
  delivered_at: string | null;
  created_at: string;
}

export interface MemoryRow {
  id: string;
  kind: string;
  subject: string | null;
  content: string;
  source: string | null;
  client_id: string | null;
  importance: number;
  confidence: string;
  tags: string[];
  hit_count: number;
  last_used_at: string | null;
  active: boolean;
  created_at: string;
}

export interface EmailRow {
  id: string;
  gmail_id: string;
  thread_id: string | null;
  from_email: string | null;
  from_name: string | null;
  subject: string | null;
  snippet: string | null;
  body_preview: string | null;
  received_at: string | null;
  is_unread: boolean;
  category: string | null;
  priority: "urgent" | "high" | "normal" | "low" | "ignore" | null;
  needs_reply: boolean;
  summary: string | null;
  suggested_action: string | null;
  client_id: string | null;
  processed_at: string | null;
}

export interface RevenueEvent {
  id: string;
  stripe_id: string;
  type: string;
  amount_cents: string;
  currency: string;
  status: string | null;
  customer_email: string | null;
  customer_name: string | null;
  stripe_customer_id: string | null;
  client_id: string | null;
  description: string | null;
  occurred_at: string;
}

export interface Alert {
  id: string;
  severity: "info" | "warn" | "urgent";
  title: string;
  body: string | null;
  category: string | null;
  client_id: string | null;
  sent_telegram: boolean;
  acknowledged: boolean;
  created_at: string;
}

export interface Task {
  id: string;
  title: string;
  detail: string | null;
  status: "open" | "doing" | "done" | "dropped";
  priority: "urgent" | "high" | "normal" | "low";
  client_id: string | null;
  due_at: string | null;
  source: string | null;
  completed_at: string | null;
  created_at: string;
}
