import { sql, one } from "../db";

/**
 * Gmail — read-only sync of recent mail into Postgres.
 *
 * Auth is Google OAuth 2.0 with an offline refresh token stored in
 * integration_tokens. Scope is gmail.readonly — VERA reads and triages; she
 * never sends. Drafting a reply is a separate, explicitly-approved action.
 *
 * Setup:
 *   1. console.cloud.google.com → new project
 *   2. Enable the Gmail API
 *   3. OAuth consent screen → External → add your own email as a test user
 *   4. Credentials → OAuth client ID → Web application
 *      Authorized redirect URI: https://<your-app>.vercel.app/api/oauth/google/callback
 *   5. Copy client ID + secret → GOOGLE_CLIENT_ID / GOOGLE_CLIENT_SECRET
 *   6. Visit /settings in the app and click Connect Gmail
 */

const OAUTH = "https://oauth2.googleapis.com/token";
const GMAIL = "https://gmail.googleapis.com/gmail/v1/users/me";

export const GMAIL_SCOPES = [
  "https://www.googleapis.com/auth/gmail.readonly",
  "https://www.googleapis.com/auth/userinfo.email",
].join(" ");

export function gmailConfigured(): boolean {
  return Boolean(process.env.GOOGLE_CLIENT_ID && process.env.GOOGLE_CLIENT_SECRET);
}

export function authUrl(redirectUri: string, state: string): string {
  const p = new URLSearchParams({
    client_id: process.env.GOOGLE_CLIENT_ID!,
    redirect_uri: redirectUri,
    response_type: "code",
    scope: GMAIL_SCOPES,
    access_type: "offline",
    prompt: "consent", // force a refresh_token even on re-auth
    state,
  });
  return `https://accounts.google.com/o/oauth2/v2/auth?${p}`;
}

export async function exchangeCode(
  code: string,
  redirectUri: string,
): Promise<void> {
  const res = await fetch(OAUTH, {
    method: "POST",
    headers: { "Content-Type": "application/x-www-form-urlencoded" },
    body: new URLSearchParams({
      code,
      client_id: process.env.GOOGLE_CLIENT_ID!,
      client_secret: process.env.GOOGLE_CLIENT_SECRET!,
      redirect_uri: redirectUri,
      grant_type: "authorization_code",
    }),
  });
  if (!res.ok) throw new Error(`Token exchange failed: ${await res.text()}`);

  const tok = (await res.json()) as {
    access_token: string;
    refresh_token?: string;
    expires_in: number;
    scope: string;
  };

  let email: string | null = null;
  try {
    const me = await fetch(`${GMAIL}/profile`, {
      headers: { Authorization: `Bearer ${tok.access_token}` },
    });
    if (me.ok) email = ((await me.json()) as { emailAddress?: string }).emailAddress ?? null;
  } catch {
    /* non-fatal */
  }

  await sql(
    `INSERT INTO integration_tokens
       (provider, access_token, refresh_token, expires_at, scope, account_email, updated_at)
     VALUES ('google',$1,$2, now() + ($3 || ' seconds')::interval, $4, $5, now())
     ON CONFLICT (provider) DO UPDATE SET
       access_token  = EXCLUDED.access_token,
       refresh_token = COALESCE(EXCLUDED.refresh_token, integration_tokens.refresh_token),
       expires_at    = EXCLUDED.expires_at,
       scope         = EXCLUDED.scope,
       account_email = COALESCE(EXCLUDED.account_email, integration_tokens.account_email),
       updated_at    = now()`,
    [tok.access_token, tok.refresh_token ?? null, tok.expires_in, tok.scope, email],
  );
}

/** Valid access token, refreshing when expired. Null when not connected. */
async function accessToken(): Promise<string | null> {
  const row = await one<{
    access_token: string | null;
    refresh_token: string | null;
    expires_at: string | null;
  }>(`SELECT access_token, refresh_token, expires_at FROM integration_tokens
       WHERE provider = 'google'`);

  if (!row?.refresh_token) return null;

  const stillValid =
    row.access_token &&
    row.expires_at &&
    new Date(row.expires_at).getTime() > Date.now() + 60_000;
  if (stillValid) return row.access_token;

  const res = await fetch(OAUTH, {
    method: "POST",
    headers: { "Content-Type": "application/x-www-form-urlencoded" },
    body: new URLSearchParams({
      refresh_token: row.refresh_token,
      client_id: process.env.GOOGLE_CLIENT_ID!,
      client_secret: process.env.GOOGLE_CLIENT_SECRET!,
      grant_type: "refresh_token",
    }),
  });
  if (!res.ok) {
    console.error("[gmail] refresh failed:", (await res.text()).slice(0, 300));
    return null;
  }

  const tok = (await res.json()) as { access_token: string; expires_in: number };
  await sql(
    `UPDATE integration_tokens
        SET access_token = $1,
            expires_at = now() + ($2 || ' seconds')::interval,
            updated_at = now()
      WHERE provider = 'google'`,
    [tok.access_token, tok.expires_in],
  );
  return tok.access_token;
}

export async function gmailStatus(): Promise<{
  connected: boolean;
  email: string | null;
}> {
  const row = await one<{ account_email: string | null; refresh_token: string | null }>(
    `SELECT account_email, refresh_token FROM integration_tokens WHERE provider='google'`,
  );
  return { connected: Boolean(row?.refresh_token), email: row?.account_email ?? null };
}

export async function disconnectGmail(): Promise<void> {
  await sql(`DELETE FROM integration_tokens WHERE provider = 'google'`);
}

interface GmailMessage {
  id: string;
  threadId: string;
  snippet?: string;
  labelIds?: string[];
  internalDate?: string;
  payload?: {
    headers?: { name: string; value: string }[];
    body?: { data?: string };
    parts?: GmailMessage["payload"][];
  };
}

/**
 * Pull recent messages into the emails table.
 * Idempotent — ON CONFLICT on gmail_id means re-running is safe.
 */
export async function syncInbox(opts: { days?: number; max?: number } = {}): Promise<{
  fetched: number;
  inserted: number;
}> {
  const token = await accessToken();
  if (!token) return { fetched: 0, inserted: 0 };

  const days = opts.days ?? 3;
  const max = Math.min(opts.max ?? 40, 100);
  const auth = { Authorization: `Bearer ${token}` };

  const listRes = await fetch(
    `${GMAIL}/messages?q=${encodeURIComponent(
      `newer_than:${days}d -in:chats -category:promotions -category:social`,
    )}&maxResults=${max}`,
    { headers: auth },
  );
  if (!listRes.ok) {
    console.error("[gmail] list failed:", (await listRes.text()).slice(0, 300));
    return { fetched: 0, inserted: 0 };
  }

  const list = (await listRes.json()) as { messages?: { id: string }[] };
  const ids = (list.messages ?? []).map((m) => m.id);
  if (!ids.length) return { fetched: 0, inserted: 0 };

  // Skip anything already stored before spending quota on full fetches.
  const known = await sql<{ gmail_id: string }>(
    `SELECT gmail_id FROM emails WHERE gmail_id = ANY($1::text[])`,
    [ids],
  );
  const seen = new Set(known.map((k) => k.gmail_id));
  const fresh = ids.filter((id) => !seen.has(id));

  let inserted = 0;
  for (const id of fresh) {
    try {
      const r = await fetch(`${GMAIL}/messages/${id}?format=full`, { headers: auth });
      if (!r.ok) continue;
      const m = (await r.json()) as GmailMessage;

      const h = (n: string) =>
        m.payload?.headers?.find((x) => x.name.toLowerCase() === n.toLowerCase())?.value ??
        null;

      const rawFrom = h("From") ?? "";
      const match = rawFrom.match(/^(.*?)\s*<(.+?)>$/);
      const fromName = match ? match[1].replace(/^"|"$/g, "").trim() : null;
      const fromEmail = (match ? match[2] : rawFrom).trim().toLowerCase();

      await sql(
        `INSERT INTO emails
           (gmail_id, thread_id, from_email, from_name, to_email, subject,
            snippet, body_preview, received_at, is_unread)
         VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10)
         ON CONFLICT (gmail_id) DO NOTHING`,
        [
          m.id,
          m.threadId,
          fromEmail || null,
          fromName,
          h("To"),
          h("Subject"),
          m.snippet ?? null,
          extractBody(m).slice(0, 4000) || null,
          m.internalDate ? new Date(Number(m.internalDate)) : null,
          (m.labelIds ?? []).includes("UNREAD"),
        ],
      );
      inserted++;
    } catch (err) {
      console.error(`[gmail] message ${id} failed:`, err);
    }
  }

  await attributeToClients();
  return { fetched: ids.length, inserted };
}

/** Link emails to clients by sender domain or contact email. */
async function attributeToClients(): Promise<void> {
  await sql(
    `UPDATE emails e SET client_id = c.id
       FROM clients c
      WHERE e.client_id IS NULL
        AND c.contact_email IS NOT NULL
        AND lower(e.from_email) = lower(c.contact_email)`,
  );
  await sql(
    `UPDATE emails e SET client_id = c.id
       FROM clients c
      WHERE e.client_id IS NULL
        AND c.website IS NOT NULL
        AND e.from_email LIKE '%@' || regexp_replace(
              regexp_replace(c.website, '^https?://(www\\.)?', ''), '/.*$', '')`,
  );
}

function extractBody(m: GmailMessage): string {
  const decode = (d?: string) =>
    d ? Buffer.from(d.replace(/-/g, "+").replace(/_/g, "/"), "base64").toString("utf8") : "";

  const walk = (part: GmailMessage["payload"]): string => {
    if (!part) return "";
    if (part.body?.data) return decode(part.body.data);
    for (const p of part.parts ?? []) {
      const got = walk(p);
      if (got) return got;
    }
    return "";
  };

  return walk(m.payload)
    .replace(/<[^>]+>/g, " ")
    .replace(/\s+/g, " ")
    .trim();
}
