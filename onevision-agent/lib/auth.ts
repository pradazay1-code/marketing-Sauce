import { cookies } from "next/headers";
import { createHmac, timingSafeEqual } from "crypto";

/**
 * Single-user auth. This app holds the whole business — it should never be
 * reachable without the password.
 *
 * Session is an HMAC-signed cookie: <expiryMs>.<signature>. No DB round-trip,
 * no session table, and it cannot be forged without CRON_SECRET.
 */

const COOKIE = "vera_session";
const TTL_MS = 30 * 24 * 60 * 60 * 1000; // 30 days

function signingKey(): string {
  const key = process.env.CRON_SECRET || process.env.DASHBOARD_PASSWORD;
  if (!key) throw new Error("CRON_SECRET or DASHBOARD_PASSWORD must be set.");
  return key;
}

function sign(payload: string): string {
  return createHmac("sha256", signingKey()).update(payload).digest("hex");
}

function safeEqual(a: string, b: string): boolean {
  const ba = Buffer.from(a);
  const bb = Buffer.from(b);
  if (ba.length !== bb.length) return false;
  return timingSafeEqual(ba, bb);
}

export function mintToken(): { value: string; maxAge: number } {
  const expiry = String(Date.now() + TTL_MS);
  return { value: `${expiry}.${sign(expiry)}`, maxAge: TTL_MS / 1000 };
}

export function verifyToken(token: string | undefined): boolean {
  if (!token) return false;
  const [expiry, sig] = token.split(".");
  if (!expiry || !sig) return false;
  if (!/^\d+$/.test(expiry)) return false;
  if (Number(expiry) < Date.now()) return false;
  try {
    return safeEqual(sig, sign(expiry));
  } catch {
    return false;
  }
}

export function checkPassword(input: string): boolean {
  const expected = process.env.DASHBOARD_PASSWORD;
  if (!expected) return false;
  try {
    return safeEqual(input, expected);
  } catch {
    return false;
  }
}

/** Server-component / route-handler guard. */
export async function isAuthed(): Promise<boolean> {
  const jar = await cookies();
  return verifyToken(jar.get(COOKIE)?.value);
}

export const SESSION_COOKIE = COOKIE;

/** Guard for cron endpoints — Vercel sends CRON_SECRET as a bearer token. */
export function isCronAuthorized(req: Request): boolean {
  const secret = process.env.CRON_SECRET;
  if (!secret) return false;
  const header = req.headers.get("authorization") ?? "";
  if (header === `Bearer ${secret}`) return true;
  // Vercel Cron also identifies itself by user-agent on some plans.
  return req.headers.get("x-vercel-cron") !== null;
}
