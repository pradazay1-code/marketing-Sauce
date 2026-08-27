import { NextResponse } from "next/server";
import { isAuthed } from "@/lib/auth";
import { sql } from "@/lib/db";

export const runtime = "nodejs";
export const maxDuration = 60;

/**
 * Preflight check. Tells you exactly which pieces are wired and which are not.
 *
 * Access: an authenticated session, or ?secret=<CRON_SECRET> so it still works
 * before you can log in. Never returns secret values — only whether they are set
 * and whether they work.
 */

interface Check {
  name: string;
  required: boolean;
  ok: boolean;
  detail: string;
  fix?: string;
}

export async function GET(req: Request) {
  const url = new URL(req.url);
  const bySecret =
    process.env.CRON_SECRET &&
    url.searchParams.get("secret") === process.env.CRON_SECRET;

  if (!bySecret && !(await isAuthed())) {
    return NextResponse.json(
      {
        status: "up",
        detail:
          "Add ?secret=<CRON_SECRET> or sign in to see the full preflight report.",
      },
      { status: 200 },
    );
  }

  const checks: Check[] = [];

  // ---- env presence ----
  const envs: [string, boolean, string][] = [
    ["DATABASE_URL", true, "Postgres connection"],
    ["ANTHROPIC_API_KEY", true, "Claude API access"],
    ["DASHBOARD_PASSWORD", true, "Login password"],
    ["CRON_SECRET", true, "Cron auth + session signing"],
    ["TELEGRAM_BOT_TOKEN", false, "Telegram alerts"],
    ["TELEGRAM_CHAT_ID", false, "Telegram destination"],
    ["STRIPE_SECRET_KEY", false, "Revenue sync"],
    ["GOOGLE_CLIENT_ID", false, "Gmail OAuth"],
    ["GOOGLE_CLIENT_SECRET", false, "Gmail OAuth"],
  ];

  for (const [key, required, what] of envs) {
    const set = Boolean(process.env[key]);
    checks.push({
      name: `env: ${key}`,
      required,
      ok: set,
      detail: set ? `set — ${what}` : `not set — ${what}`,
      fix: set ? undefined : `Add ${key} in Vercel → Settings → Environment Variables`,
    });
  }

  // ---- database reachable ----
  let dbOk = false;
  try {
    await sql("SELECT 1");
    dbOk = true;
    checks.push({
      name: "database: connection",
      required: true,
      ok: true,
      detail: "connected",
    });
  } catch (err) {
    checks.push({
      name: "database: connection",
      required: true,
      ok: false,
      detail: err instanceof Error ? err.message.slice(0, 180) : "failed",
      fix: "Check DATABASE_URL. Neon and Supabase strings must include ?sslmode=require",
    });
  }

  // ---- schema applied ----
  if (dbOk) {
    const expected = [
      "clients", "deliverables", "memory", "emails",
      "revenue_events", "conversations", "messages",
      "alerts", "tasks", "job_runs", "integration_tokens",
    ];
    try {
      const rows = await sql<{ table_name: string }>(
        `SELECT table_name FROM information_schema.tables
          WHERE table_schema = 'public'`,
      );
      const have = new Set(rows.map((r) => r.table_name));
      const missing = expected.filter((t) => !have.has(t));
      checks.push({
        name: "database: schema",
        required: true,
        ok: missing.length === 0,
        detail:
          missing.length === 0
            ? `all ${expected.length} tables present`
            : `missing: ${missing.join(", ")}`,
        fix: missing.length ? "Run db/schema.sql against your database" : undefined,
      });

      if (missing.length === 0) {
        const [counts] = await sql<{ clients: number; memory: number }>(
          `SELECT (SELECT count(*) FROM clients)::int AS clients,
                  (SELECT count(*) FROM memory WHERE active)::int AS memory`,
        );
        checks.push({
          name: "database: seed data",
          required: false,
          ok: counts.clients > 0,
          detail: `${counts.clients} clients, ${counts.memory} memory facts`,
          fix: counts.clients === 0 ? "Re-run db/schema.sql to load seed rows" : undefined,
        });
      }
    } catch (err) {
      checks.push({
        name: "database: schema",
        required: true,
        ok: false,
        detail: err instanceof Error ? err.message.slice(0, 180) : "check failed",
      });
    }
  }

  // ---- Anthropic reachable ----
  if (process.env.ANTHROPIC_API_KEY) {
    try {
      const res = await fetch("https://api.anthropic.com/v1/models?limit=1", {
        headers: {
          "x-api-key": process.env.ANTHROPIC_API_KEY,
          "anthropic-version": "2023-06-01",
        },
      });
      checks.push({
        name: "anthropic: key",
        required: true,
        ok: res.ok,
        detail: res.ok ? "key accepted" : `rejected (HTTP ${res.status})`,
        fix: res.ok ? undefined : "Verify the key at console.anthropic.com",
      });
    } catch {
      checks.push({
        name: "anthropic: key",
        required: true,
        ok: false,
        detail: "network error reaching api.anthropic.com",
      });
    }
  }

  // ---- Telegram reachable ----
  if (process.env.TELEGRAM_BOT_TOKEN) {
    try {
      const res = await fetch(
        `https://api.telegram.org/bot${process.env.TELEGRAM_BOT_TOKEN}/getMe`,
      );
      const body = (await res.json()) as { ok?: boolean; result?: { username?: string } };
      checks.push({
        name: "telegram: bot",
        required: false,
        ok: Boolean(body.ok),
        detail: body.ok ? `@${body.result?.username ?? "connected"}` : "token rejected",
        fix: body.ok ? undefined : "Re-copy the token from @BotFather",
      });
    } catch {
      checks.push({
        name: "telegram: bot",
        required: false,
        ok: false,
        detail: "network error",
      });
    }
  }

  // ---- Stripe reachable ----
  if (process.env.STRIPE_SECRET_KEY) {
    try {
      const res = await fetch("https://api.stripe.com/v1/charges?limit=1", {
        headers: { Authorization: `Bearer ${process.env.STRIPE_SECRET_KEY}` },
      });
      checks.push({
        name: "stripe: key",
        required: false,
        ok: res.ok,
        detail: res.ok
          ? `accepted (${process.env.STRIPE_SECRET_KEY.startsWith("sk_live") ? "live" : "test"} mode)`
          : `rejected (HTTP ${res.status})`,
        fix: res.ok ? undefined : "Verify the secret key in the Stripe dashboard",
      });
    } catch {
      checks.push({
        name: "stripe: key",
        required: false,
        ok: false,
        detail: "network error",
      });
    }
  }

  // ---- Gmail connected ----
  if (dbOk) {
    try {
      const [tok] = await sql<{ account_email: string | null }>(
        `SELECT account_email FROM integration_tokens
          WHERE provider='google' AND refresh_token IS NOT NULL`,
      );
      checks.push({
        name: "gmail: oauth",
        required: false,
        ok: Boolean(tok),
        detail: tok ? `connected as ${tok.account_email ?? "unknown"}` : "not connected",
        fix: tok ? undefined : "Open /settings and click Connect Gmail",
      });
    } catch {
      /* schema not applied — already reported above */
    }
  }

  const failedRequired = checks.filter((c) => c.required && !c.ok);
  const failedOptional = checks.filter((c) => !c.required && !c.ok);

  return NextResponse.json(
    {
      status: failedRequired.length === 0 ? "ready" : "not ready",
      summary:
        failedRequired.length === 0
          ? `All required checks pass. ${failedOptional.length} optional integration${failedOptional.length === 1 ? "" : "s"} not configured.`
          : `${failedRequired.length} required check${failedRequired.length === 1 ? "" : "s"} failing — VERA will not run correctly.`,
      blocking: failedRequired.map((c) => ({ check: c.name, detail: c.detail, fix: c.fix })),
      checks,
      checked_at: new Date().toISOString(),
    },
    { status: failedRequired.length === 0 ? 200 : 503 },
  );
}
