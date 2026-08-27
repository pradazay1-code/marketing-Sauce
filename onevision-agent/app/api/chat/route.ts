import { NextResponse } from "next/server";
import { isAuthed } from "@/lib/auth";
import { runAgent } from "@/lib/agent/run";

export const runtime = "nodejs";
export const maxDuration = 300;

export async function POST(req: Request) {
  if (!(await isAuthed())) {
    return NextResponse.json({ error: "Not authenticated" }, { status: 401 });
  }

  let body: { message?: string; conversationId?: string };
  try {
    body = await req.json();
  } catch {
    return NextResponse.json({ error: "Invalid JSON" }, { status: 400 });
  }

  const message = (body.message ?? "").trim();
  if (!message) {
    return NextResponse.json({ error: "message is required" }, { status: 400 });
  }
  if (message.length > 12_000) {
    return NextResponse.json({ error: "Message too long" }, { status: 400 });
  }

  try {
    const result = await runAgent({
      message,
      conversationId: body.conversationId,
      channel: "web",
    });
    return NextResponse.json(result);
  } catch (err) {
    const msg = err instanceof Error ? err.message : String(err);
    console.error("[api/chat]", err);
    return NextResponse.json({ error: msg }, { status: 500 });
  }
}
