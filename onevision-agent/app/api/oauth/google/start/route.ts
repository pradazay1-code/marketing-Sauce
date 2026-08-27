import { NextResponse } from "next/server";
import { isAuthed } from "@/lib/auth";
import { authUrl, gmailConfigured } from "@/lib/integrations/gmail";
import { createHmac } from "crypto";

export const runtime = "nodejs";

export async function GET(req: Request) {
  if (!(await isAuthed())) {
    return NextResponse.redirect(new URL("/login", req.url));
  }
  if (!gmailConfigured()) {
    return NextResponse.json(
      { error: "GOOGLE_CLIENT_ID / GOOGLE_CLIENT_SECRET are not set." },
      { status: 400 },
    );
  }

  const url = new URL(req.url);
  const redirectUri = `${url.protocol}//${url.host}/api/oauth/google/callback`;

  // Signed state so the callback can verify the round-trip came from us.
  const nonce = String(Date.now());
  const sig = createHmac("sha256", process.env.CRON_SECRET || "vera")
    .update(nonce)
    .digest("hex")
    .slice(0, 24);

  return NextResponse.redirect(authUrl(redirectUri, `${nonce}.${sig}`));
}
