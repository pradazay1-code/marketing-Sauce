import { NextResponse } from "next/server";
import { exchangeCode } from "@/lib/integrations/gmail";
import { createHmac, timingSafeEqual } from "crypto";

export const runtime = "nodejs";

export async function GET(req: Request) {
  const url = new URL(req.url);
  const code = url.searchParams.get("code");
  const state = url.searchParams.get("state") ?? "";
  const error = url.searchParams.get("error");

  if (error) {
    return NextResponse.redirect(new URL(`/settings?gmail=denied`, req.url));
  }
  if (!code) {
    return NextResponse.redirect(new URL(`/settings?gmail=nocode`, req.url));
  }

  // Verify state
  const [nonce, sig] = state.split(".");
  const expected = createHmac("sha256", process.env.CRON_SECRET || "vera")
    .update(nonce ?? "")
    .digest("hex")
    .slice(0, 24);
  const valid =
    sig &&
    sig.length === expected.length &&
    timingSafeEqual(Buffer.from(sig), Buffer.from(expected));

  if (!valid) {
    return NextResponse.redirect(new URL(`/settings?gmail=badstate`, req.url));
  }

  try {
    const redirectUri = `${url.protocol}//${url.host}/api/oauth/google/callback`;
    await exchangeCode(code, redirectUri);
    return NextResponse.redirect(new URL(`/settings?gmail=connected`, req.url));
  } catch (err) {
    console.error("[oauth/google]", err);
    return NextResponse.redirect(new URL(`/settings?gmail=failed`, req.url));
  }
}
