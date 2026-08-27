import type Anthropic from "@anthropic-ai/sdk";
import { sql, one, type Client } from "../db";
import { remember, recall, memoriesForClient } from "./memory";
import { sendTelegram } from "../integrations/telegram";

/**
 * VERA's tool surface.
 *
 * Definitions are a frozen, deterministically-ordered array — they render before
 * the system prompt in the request, so any change here invalidates the prompt
 * cache for every subsequent block. Add new tools at the END of the array.
 */

export const TOOLS: Anthropic.Tool[] = [
  {
    name: "list_clients",
    description:
      "List clients with their status and health score. Use this for any question about who the clients are, how many there are, or which are at risk. Returns all clients when no filter is given.",
    input_schema: {
      type: "object",
      properties: {
        status: {
          type: "string",
          enum: ["prospect", "onboarding", "active", "paused", "churned"],
          description: "Filter by lifecycle status.",
        },
        at_risk_only: {
          type: "boolean",
          description: "Only return clients with a health score below 60.",
        },
      },
    },
  },
  {
    name: "get_client",
    description:
      "Full detail on one client: profile, health, every deliverable, recent revenue, recent email, and stored memory about them. Use before answering anything specific about a client.",
    input_schema: {
      type: "object",
      properties: {
        name_or_slug: {
          type: "string",
          description: "Client name or slug. Partial names match.",
        },
      },
      required: ["name_or_slug"],
    },
  },
  {
    name: "update_client",
    description:
      "Update a client's health score, health notes, status, or general notes after reviewing their account. Use this when you complete a client review.",
    input_schema: {
      type: "object",
      properties: {
        name_or_slug: { type: "string" },
        health_score: {
          type: "integer",
          description: "0-100. Below 60 flags the client as at risk.",
        },
        health_notes: {
          type: "string",
          description: "Short plain-language reason for the score.",
        },
        status: {
          type: "string",
          enum: ["prospect", "onboarding", "active", "paused", "churned"],
        },
        notes: { type: "string" },
        mark_reviewed: {
          type: "boolean",
          description: "Set the last-reviewed timestamp to now.",
        },
      },
      required: ["name_or_slug"],
    },
  },
  {
    name: "list_deliverables",
    description:
      "List work items. Filter by client or status. Use to answer what has been delivered, what is in flight, and what is overdue.",
    input_schema: {
      type: "object",
      properties: {
        name_or_slug: { type: "string", description: "Limit to one client." },
        status: {
          type: "string",
          enum: ["planned", "in_progress", "delivered", "blocked", "cancelled"],
        },
        overdue_only: { type: "boolean" },
      },
    },
  },
  {
    name: "upsert_deliverable",
    description:
      "Create a new deliverable or update an existing one by id. Use when Isaiah reports work completed or new work committed.",
    input_schema: {
      type: "object",
      properties: {
        id: { type: "string", description: "Omit to create a new deliverable." },
        name_or_slug: { type: "string", description: "Required when creating." },
        title: { type: "string" },
        kind: {
          type: "string",
          enum: ["website", "content", "ad_campaign", "seo", "crm", "report", "other"],
        },
        status: {
          type: "string",
          enum: ["planned", "in_progress", "delivered", "blocked", "cancelled"],
        },
        detail: { type: "string" },
        url: { type: "string" },
        due_at: { type: "string", description: "YYYY-MM-DD" },
      },
    },
  },
  {
    name: "get_revenue",
    description:
      "Revenue summary from Stripe records: totals over a window, month-over-month movement, failed payments, and per-client breakdown.",
    input_schema: {
      type: "object",
      properties: {
        days: {
          type: "integer",
          description: "Look-back window in days. Default 30.",
        },
        by_client: { type: "boolean", description: "Break the total down per client." },
      },
    },
  },
  {
    name: "search_emails",
    description:
      "Search synced email. Use to answer what has come in, what needs a reply, and what a specific person last said.",
    input_schema: {
      type: "object",
      properties: {
        query: { type: "string", description: "Match against subject, sender, and body." },
        needs_reply_only: { type: "boolean" },
        priority: {
          type: "string",
          enum: ["urgent", "high", "normal", "low", "ignore"],
        },
        days: { type: "integer", description: "Look-back window. Default 14." },
        limit: { type: "integer" },
      },
    },
  },
  {
    name: "search_memory",
    description:
      "Search your own long-term knowledge base about the business. Use before saying you do not know something — you may already have recorded it.",
    input_schema: {
      type: "object",
      properties: {
        query: { type: "string" },
        limit: { type: "integer" },
      },
      required: ["query"],
    },
  },
  {
    name: "remember",
    description:
      "Store a durable fact, decision, preference, lesson, or process in long-term memory. Use when you learn something that should outlive this conversation. Do not store transient chatter.",
    input_schema: {
      type: "object",
      properties: {
        content: { type: "string", description: "The fact, written to stand alone." },
        kind: {
          type: "string",
          enum: [
            "fact",
            "preference",
            "decision",
            "lesson",
            "process",
            "person",
            "metric",
            "risk",
          ],
        },
        subject: {
          type: "string",
          description: "What this is about — a client name, 'pricing', 'Isaiah', etc.",
        },
        importance: { type: "integer", description: "1-5. Default 3." },
        tags: { type: "array", items: { type: "string" } },
        name_or_slug: {
          type: "string",
          description: "Attach the memory to a client, if relevant.",
        },
      },
      required: ["content"],
    },
  },
  {
    name: "list_tasks",
    description: "List Isaiah's tasks. Use to answer what is open, overdue, or urgent.",
    input_schema: {
      type: "object",
      properties: {
        status: { type: "string", enum: ["open", "doing", "done", "dropped"] },
        overdue_only: { type: "boolean" },
      },
    },
  },
  {
    name: "create_task",
    description:
      "Create a task for Isaiah. Use when something needs doing and would otherwise be forgotten.",
    input_schema: {
      type: "object",
      properties: {
        title: { type: "string" },
        detail: { type: "string" },
        priority: { type: "string", enum: ["urgent", "high", "normal", "low"] },
        due_at: { type: "string", description: "YYYY-MM-DD" },
        name_or_slug: { type: "string", description: "Attach to a client." },
      },
      required: ["title"],
    },
  },
  {
    name: "complete_task",
    description: "Mark a task done or dropped.",
    input_schema: {
      type: "object",
      properties: {
        id: { type: "string" },
        status: { type: "string", enum: ["done", "dropped"] },
      },
      required: ["id"],
    },
  },
  {
    name: "raise_alert",
    description:
      "Record an alert on the dashboard. Set notify_telegram to also push it to Isaiah's phone — reserve that for things that genuinely cannot wait.",
    input_schema: {
      type: "object",
      properties: {
        title: { type: "string" },
        body: { type: "string" },
        severity: { type: "string", enum: ["info", "warn", "urgent"] },
        category: {
          type: "string",
          enum: ["revenue", "client", "inbox", "task", "system"],
        },
        name_or_slug: { type: "string" },
        notify_telegram: { type: "boolean" },
      },
      required: ["title"],
    },
  },
  {
    name: "query_database",
    description:
      "Run a read-only SQL SELECT against the business database when no other tool fits. Tables: clients, deliverables, memory, emails, revenue_events, alerts, tasks, job_runs. Only SELECT is permitted.",
    input_schema: {
      type: "object",
      properties: {
        query: { type: "string", description: "A single SELECT statement." },
      },
      required: ["query"],
    },
  },
];

// ---------------------------------------------------------------------------
// Execution
// ---------------------------------------------------------------------------

type Json = Record<string, unknown>;

async function resolveClient(nameOrSlug?: string): Promise<Client | null> {
  if (!nameOrSlug) return null;
  return one<Client>(
    `SELECT * FROM clients
      WHERE slug = $1 OR name ILIKE $2 OR similarity(name, $1) > 0.3
      ORDER BY (slug = $1) DESC, similarity(name, $1) DESC
      LIMIT 1`,
    [nameOrSlug, `%${nameOrSlug}%`],
  );
}

export async function executeTool(name: string, input: Json): Promise<string> {
  try {
    const result = await dispatch(name, input);
    return typeof result === "string" ? result : JSON.stringify(result, null, 2);
  } catch (err) {
    const msg = err instanceof Error ? err.message : String(err);
    return JSON.stringify({ error: msg });
  }
}

async function dispatch(name: string, a: Json): Promise<unknown> {
  switch (name) {
    // ---------------- clients ----------------
    case "list_clients": {
      const where: string[] = [];
      const params: unknown[] = [];
      if (a.status) {
        params.push(a.status);
        where.push(`status = $${params.length}`);
      }
      if (a.at_risk_only) where.push(`health_score < 60`);
      const rows = await sql<Client>(
        `SELECT slug, name, contact_name, industry, city, state, status,
                monthly_value, health_score, health_notes,
                last_contact_at, last_reviewed_at
           FROM clients
          ${where.length ? "WHERE " + where.join(" AND ") : ""}
          ORDER BY health_score ASC, name ASC`,
        params,
      );
      return { count: rows.length, clients: rows };
    }

    case "get_client": {
      const c = await resolveClient(a.name_or_slug as string);
      if (!c) return { error: `No client matching "${a.name_or_slug}".` };

      const [deliverables, revenue, emails, mem] = await Promise.all([
        sql(
          `SELECT id, title, kind, status, detail, url, due_at, delivered_at
             FROM deliverables WHERE client_id = $1
            ORDER BY COALESCE(delivered_at, due_at, created_at) DESC LIMIT 40`,
          [c.id],
        ),
        sql(
          `SELECT type, amount_cents, status, occurred_at, description
             FROM revenue_events WHERE client_id = $1
            ORDER BY occurred_at DESC LIMIT 12`,
          [c.id],
        ),
        sql(
          `SELECT subject, from_email, received_at, priority, needs_reply, summary
             FROM emails WHERE client_id = $1
            ORDER BY received_at DESC LIMIT 10`,
          [c.id],
        ),
        memoriesForClient(c.id, 20),
      ]);

      return {
        client: c,
        deliverables,
        recent_revenue: revenue,
        recent_emails: emails,
        memory: mem.map((m) => ({
          kind: m.kind,
          content: m.content,
          importance: m.importance,
        })),
      };
    }

    case "update_client": {
      const c = await resolveClient(a.name_or_slug as string);
      if (!c) return { error: `No client matching "${a.name_or_slug}".` };

      const sets: string[] = [];
      const params: unknown[] = [c.id];
      const set = (col: string, val: unknown) => {
        params.push(val);
        sets.push(`${col} = $${params.length}`);
      };
      if (a.health_score !== undefined) set("health_score", a.health_score);
      if (a.health_notes !== undefined) set("health_notes", a.health_notes);
      if (a.status !== undefined) set("status", a.status);
      if (a.notes !== undefined) set("notes", a.notes);
      if (a.mark_reviewed) sets.push(`last_reviewed_at = now()`);
      if (!sets.length) return { error: "Nothing to update." };
      sets.push(`updated_at = now()`);

      const updated = await one<Client>(
        `UPDATE clients SET ${sets.join(", ")} WHERE id = $1 RETURNING *`,
        params,
      );
      return { updated };
    }

    // ---------------- deliverables ----------------
    case "list_deliverables": {
      const where: string[] = [];
      const params: unknown[] = [];
      if (a.name_or_slug) {
        const c = await resolveClient(a.name_or_slug as string);
        if (!c) return { error: `No client matching "${a.name_or_slug}".` };
        params.push(c.id);
        where.push(`d.client_id = $${params.length}`);
      }
      if (a.status) {
        params.push(a.status);
        where.push(`d.status = $${params.length}`);
      }
      if (a.overdue_only) {
        where.push(`d.due_at < CURRENT_DATE AND d.status NOT IN ('delivered','cancelled')`);
      }
      const rows = await sql(
        `SELECT d.id, c.name AS client, d.title, d.kind, d.status,
                d.detail, d.url, d.due_at, d.delivered_at
           FROM deliverables d JOIN clients c ON c.id = d.client_id
          ${where.length ? "WHERE " + where.join(" AND ") : ""}
          ORDER BY d.due_at NULLS LAST, d.created_at DESC LIMIT 100`,
        params,
      );
      return { count: rows.length, deliverables: rows };
    }

    case "upsert_deliverable": {
      if (a.id) {
        const sets: string[] = [];
        const params: unknown[] = [a.id];
        const set = (col: string, val: unknown) => {
          params.push(val);
          sets.push(`${col} = $${params.length}`);
        };
        for (const f of ["title", "kind", "status", "detail", "url", "due_at"]) {
          if (a[f] !== undefined) set(f, a[f]);
        }
        if (a.status === "delivered") sets.push(`delivered_at = now()`);
        if (!sets.length) return { error: "Nothing to update." };
        sets.push(`updated_at = now()`);
        const row = await one(
          `UPDATE deliverables SET ${sets.join(", ")} WHERE id = $1 RETURNING *`,
          params,
        );
        return { updated: row };
      }

      const c = await resolveClient(a.name_or_slug as string);
      if (!c) return { error: "name_or_slug is required when creating a deliverable." };
      const row = await one(
        `INSERT INTO deliverables (client_id, title, kind, status, detail, url, due_at, delivered_at)
         VALUES ($1,$2,$3,$4,$5,$6,$7, CASE WHEN $4 = 'delivered' THEN now() END)
         RETURNING *`,
        [
          c.id,
          a.title ?? "Untitled",
          a.kind ?? "other",
          a.status ?? "planned",
          a.detail ?? null,
          a.url ?? null,
          a.due_at ?? null,
        ],
      );
      return { created: row };
    }

    // ---------------- revenue ----------------
    case "get_revenue": {
      const days = Number(a.days ?? 30);
      const [totals] = await sql<{
        collected: string; refunded: string; failed: string; n: number;
      }>(
        `SELECT
           COALESCE(SUM(amount_cents) FILTER (WHERE type IN ('payment','invoice_paid') AND status <> 'failed'),0)::text AS collected,
           COALESCE(SUM(amount_cents) FILTER (WHERE type = 'refund'),0)::text AS refunded,
           COALESCE(SUM(amount_cents) FILTER (WHERE status = 'failed'),0)::text AS failed,
           count(*)::int AS n
         FROM revenue_events
        WHERE occurred_at > now() - ($1 || ' days')::interval`,
        [days],
      );

      const [prior] = await sql<{ collected: string }>(
        `SELECT COALESCE(SUM(amount_cents) FILTER (WHERE type IN ('payment','invoice_paid') AND status <> 'failed'),0)::text AS collected
           FROM revenue_events
          WHERE occurred_at > now() - ($1 || ' days')::interval * 2
            AND occurred_at <= now() - ($1 || ' days')::interval`,
        [days],
      );

      const [mrr] = await sql<{ mrr: string }>(
        `SELECT COALESCE(SUM(monthly_value),0)::text AS mrr
           FROM clients WHERE status = 'active'`,
      );

      const out: Json = {
        window_days: days,
        collected_usd: Number(totals.collected) / 100,
        refunded_usd: Number(totals.refunded) / 100,
        failed_usd: Number(totals.failed) / 100,
        prior_period_usd: Number(prior.collected) / 100,
        contracted_mrr_usd: Number(mrr.mrr),
        event_count: totals.n,
      };

      if (a.by_client) {
        out.by_client = await sql(
          `SELECT COALESCE(c.name, r.customer_email, 'Unattributed') AS client,
                  (SUM(r.amount_cents)/100.0)::float AS usd,
                  count(*)::int AS events
             FROM revenue_events r LEFT JOIN clients c ON c.id = r.client_id
            WHERE r.occurred_at > now() - ($1 || ' days')::interval
              AND r.type IN ('payment','invoice_paid')
            GROUP BY 1 ORDER BY 2 DESC`,
          [days],
        );
      }
      return out;
    }

    // ---------------- email ----------------
    case "search_emails": {
      const days = Number(a.days ?? 14);
      const limit = Math.min(Number(a.limit ?? 25), 100);
      const where = [`received_at > now() - ($1 || ' days')::interval`];
      const params: unknown[] = [days];
      if (a.query) {
        params.push(`%${a.query}%`);
        where.push(
          `(subject ILIKE $${params.length} OR from_email ILIKE $${params.length}
            OR from_name ILIKE $${params.length} OR body_preview ILIKE $${params.length})`,
        );
      }
      if (a.needs_reply_only) where.push(`needs_reply = true`);
      if (a.priority) {
        params.push(a.priority);
        where.push(`priority = $${params.length}`);
      }
      params.push(limit);
      const rows = await sql(
        `SELECT from_name, from_email, subject, snippet, summary, priority,
                category, needs_reply, suggested_action, received_at
           FROM emails WHERE ${where.join(" AND ")}
          ORDER BY received_at DESC LIMIT $${params.length}`,
        params,
      );
      return { count: rows.length, emails: rows };
    }

    // ---------------- memory ----------------
    case "search_memory": {
      const rows = await recall(String(a.query), Number(a.limit ?? 12));
      return {
        count: rows.length,
        memories: rows.map((m) => ({
          id: m.id,
          kind: m.kind,
          subject: m.subject,
          content: m.content,
          importance: m.importance,
          recorded: m.created_at,
        })),
      };
    }

    case "remember": {
      let clientId: string | null = null;
      if (a.name_or_slug) {
        const c = await resolveClient(a.name_or_slug as string);
        clientId = c?.id ?? null;
      }
      const row = await remember({
        content: String(a.content),
        kind: (a.kind as string) ?? "fact",
        subject: (a.subject as string) ?? undefined,
        source: "agent",
        clientId,
        importance: Number(a.importance ?? 3),
        tags: (a.tags as string[]) ?? [],
      });
      return { stored: { id: row.id, content: row.content, kind: row.kind } };
    }

    // ---------------- tasks ----------------
    case "list_tasks": {
      const where: string[] = [];
      const params: unknown[] = [];
      if (a.status) {
        params.push(a.status);
        where.push(`t.status = $${params.length}`);
      } else {
        where.push(`t.status IN ('open','doing')`);
      }
      if (a.overdue_only) where.push(`t.due_at < CURRENT_DATE`);
      const rows = await sql(
        `SELECT t.id, t.title, t.detail, t.status, t.priority, t.due_at,
                c.name AS client, t.created_at
           FROM tasks t LEFT JOIN clients c ON c.id = t.client_id
          ${where.length ? "WHERE " + where.join(" AND ") : ""}
          ORDER BY
            CASE t.priority WHEN 'urgent' THEN 0 WHEN 'high' THEN 1
                            WHEN 'normal' THEN 2 ELSE 3 END,
            t.due_at NULLS LAST
          LIMIT 100`,
        params,
      );
      return { count: rows.length, tasks: rows };
    }

    case "create_task": {
      let clientId: string | null = null;
      if (a.name_or_slug) {
        const c = await resolveClient(a.name_or_slug as string);
        clientId = c?.id ?? null;
      }
      const row = await one(
        `INSERT INTO tasks (title, detail, priority, due_at, client_id, source)
         VALUES ($1,$2,$3,$4,$5,'agent') RETURNING *`,
        [
          a.title,
          a.detail ?? null,
          a.priority ?? "normal",
          a.due_at ?? null,
          clientId,
        ],
      );
      return { created: row };
    }

    case "complete_task": {
      const row = await one(
        `UPDATE tasks SET status = $2,
                completed_at = CASE WHEN $2 = 'done' THEN now() END
          WHERE id = $1 RETURNING *`,
        [a.id, a.status ?? "done"],
      );
      return row ? { updated: row } : { error: "Task not found." };
    }

    // ---------------- alerts ----------------
    case "raise_alert": {
      let clientId: string | null = null;
      if (a.name_or_slug) {
        const c = await resolveClient(a.name_or_slug as string);
        clientId = c?.id ?? null;
      }
      const row = await one<{ id: string }>(
        `INSERT INTO alerts (title, body, severity, category, client_id)
         VALUES ($1,$2,$3,$4,$5) RETURNING id`,
        [
          a.title,
          a.body ?? null,
          a.severity ?? "info",
          a.category ?? null,
          clientId,
        ],
      );

      let delivered = false;
      if (a.notify_telegram) {
        const icon =
          a.severity === "urgent" ? "🔴" : a.severity === "warn" ? "🟡" : "🔵";
        delivered = await sendTelegram(
          `${icon} *${a.title}*\n\n${a.body ?? ""}`.trim(),
        );
        if (delivered) {
          await sql(`UPDATE alerts SET sent_telegram = true WHERE id = $1`, [row!.id]);
        }
      }
      return { alert_id: row!.id, telegram_sent: delivered };
    }

    // ---------------- raw read-only SQL ----------------
    case "query_database": {
      const q = String(a.query ?? "").trim();
      const normalized = q.toLowerCase().replace(/\s+/g, " ");

      if (!normalized.startsWith("select") && !normalized.startsWith("with ")) {
        return { error: "Only SELECT queries are permitted." };
      }
      // Reject anything that could mutate, even inside a CTE.
      if (
        /\b(insert|update|delete|drop|alter|truncate|create|grant|revoke|copy)\b/.test(
          normalized,
        )
      ) {
        return { error: "Write operations are not permitted through this tool." };
      }
      if (q.includes(";") && q.indexOf(";") < q.trimEnd().length - 1) {
        return { error: "Multiple statements are not permitted." };
      }

      const capped = /\blimit\b/.test(normalized)
        ? q.replace(/;+\s*$/, "")
        : `${q.replace(/;+\s*$/, "")} LIMIT 200`;

      const rows = await sql(capped);
      return { row_count: rows.length, rows };
    }

    default:
      return { error: `Unknown tool: ${name}` };
  }
}
