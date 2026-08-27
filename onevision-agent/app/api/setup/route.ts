import { NextResponse } from "next/server";
import { readFileSync } from "node:fs";
import { join } from "node:path";
import { pool } from "@/lib/db";

export const runtime = "nodejs";
export const maxDuration = 120;

/**
 * Apply the database schema from the deployed app.
 *
 * This exists so setup never requires a terminal, psql, or a particular
 * machine — deploy from GitHub, set env vars in the Vercel dashboard, then
 * hit this URL once in a browser.
 *
 *   /api/setup?secret=<CRON_SECRET>
 *
 * Idempotent. Safe to hit more than once.
 */
export async function GET(req: Request) {
  const url = new URL(req.url);
  const secret = process.env.CRON_SECRET;

  if (!secret) {
    return NextResponse.json(
      { error: "CRON_SECRET is not set. Add it in Vercel → Settings → Environment Variables." },
      { status: 400 },
    );
  }
  if (url.searchParams.get("secret") !== secret) {
    return NextResponse.json(
      { error: "Unauthorized. Append ?secret=<your CRON_SECRET>." },
      { status: 401 },
    );
  }
  if (!process.env.DATABASE_URL) {
    return NextResponse.json(
      { error: "DATABASE_URL is not set." },
      { status: 400 },
    );
  }

  let schema: string;
  try {
    schema = readFileSync(join(process.cwd(), "db", "schema.sql"), "utf8");
  } catch {
    return NextResponse.json(
      {
        error:
          "Could not read db/schema.sql from the deployment. Make sure the db/ folder is committed.",
      },
      { status: 500 },
    );
  }

  const client = await pool().connect();
  try {
    await client.query(schema);

    const { rows: tables } = await client.query<{ table_name: string }>(
      `SELECT table_name FROM information_schema.tables
        WHERE table_schema='public' ORDER BY table_name`,
    );
    const { rows: [counts] } = await client.query<{ clients: number; memory: number }>(
      `SELECT (SELECT count(*) FROM clients)::int AS clients,
              (SELECT count(*) FROM memory WHERE active)::int AS memory`,
    );

    return NextResponse.json({
      status: "ok",
      message: "Schema applied. VERA is ready.",
      tables: tables.map((t) => t.table_name),
      seed: { clients: counts.clients, memory_facts: counts.memory },
      next: [
        "Visit /api/health?secret=<CRON_SECRET> to confirm every integration",
        "Then open / and sign in with DASHBOARD_PASSWORD",
      ],
    });
  } catch (err) {
    const msg = err instanceof Error ? err.message : String(err);
    let hint: string | undefined;
    if (/certificate|self.signed/i.test(msg)) {
      hint = "Append ?sslmode=require to DATABASE_URL.";
    } else if (/password|authentication/i.test(msg)) {
      hint = "Re-copy the connection string from your database provider.";
    } else if (/ENOTFOUND|ETIMEDOUT|ECONNREFUSED/i.test(msg)) {
      hint = "Database host unreachable — check the hostname is correct.";
    }
    return NextResponse.json({ error: msg.slice(0, 400), hint }, { status: 500 });
  } finally {
    client.release();
  }
}
