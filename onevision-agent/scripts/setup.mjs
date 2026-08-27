#!/usr/bin/env node
/**
 * One-command database setup.
 *
 *   npm run setup
 *
 * Applies db/schema.sql to whatever DATABASE_URL points at. No psql required.
 * Idempotent — safe to run as many times as you like.
 *
 * Reads DATABASE_URL from the environment, or from .env.local / .env if present.
 */

import { readFileSync, existsSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";
import pg from "pg";

const root = join(dirname(fileURLToPath(import.meta.url)), "..");

// ---------- resolve DATABASE_URL ----------
function loadEnvFile(name) {
  const path = join(root, name);
  if (!existsSync(path)) return;
  for (const line of readFileSync(path, "utf8").split("\n")) {
    const m = line.match(/^\s*([A-Z0-9_]+)\s*=\s*(.*)\s*$/);
    if (!m) continue;
    const [, key, rawVal] = m;
    if (process.env[key]) continue;
    process.env[key] = rawVal.replace(/^["']|["']$/g, "");
  }
}

loadEnvFile(".env.local");
loadEnvFile(".env");

const url = process.env.DATABASE_URL;
if (!url) {
  console.error(`
✗ DATABASE_URL is not set.

  Either export it:
      export DATABASE_URL="postgres://..."

  Or put it in .env.local:
      DATABASE_URL=postgres://...
`);
  process.exit(1);
}

// ---------- apply schema ----------
const schemaPath = join(root, "db", "schema.sql");
if (!existsSync(schemaPath)) {
  console.error(`✗ Could not find ${schemaPath}`);
  process.exit(1);
}

const host = (() => {
  try {
    return new URL(url).host;
  } catch {
    return "(unparseable host)";
  }
})();

console.log(`\n→ Connecting to ${host}`);

const client = new pg.Client({
  connectionString: url,
  ssl: url.includes("localhost") ? undefined : { rejectUnauthorized: false },
  connectionTimeoutMillis: 15_000,
});

try {
  await client.connect();
  console.log("✓ Connected");

  console.log("→ Applying db/schema.sql");
  await client.query(readFileSync(schemaPath, "utf8"));
  console.log("✓ Schema applied");

  const { rows: tables } = await client.query(
    `SELECT table_name FROM information_schema.tables
      WHERE table_schema='public' ORDER BY table_name`,
  );
  const { rows: [counts] } = await client.query(
    `SELECT (SELECT count(*) FROM clients)::int   AS clients,
            (SELECT count(*) FROM memory)::int    AS memory`,
  );

  console.log(`\n✓ ${tables.length} tables ready:`);
  console.log(`  ${tables.map((t) => t.table_name).join(", ")}`);
  console.log(`\n✓ Seed data: ${counts.clients} clients, ${counts.memory} memory facts`);

  console.log(`
Next:
  1. Make sure these are set in Vercel → Settings → Environment Variables:
       DATABASE_URL, ANTHROPIC_API_KEY, DASHBOARD_PASSWORD, CRON_SECRET
  2. Deploy:  npx vercel --prod
  3. Verify:  https://<your-app>.vercel.app/api/health?secret=<CRON_SECRET>
`);
} catch (err) {
  console.error(`\n✗ ${err.message}`);
  if (/self.signed|certificate/i.test(err.message)) {
    console.error("  TLS issue — append ?sslmode=require to your DATABASE_URL.");
  }
  if (/password|authentication/i.test(err.message)) {
    console.error("  Auth failed — re-copy the connection string from your provider.");
  }
  if (/ENOTFOUND|ETIMEDOUT|ECONNREFUSED/i.test(err.message)) {
    console.error("  Host unreachable — check the hostname and that the database is running.");
  }
  process.exitCode = 1;
} finally {
  await client.end().catch(() => {});
}
