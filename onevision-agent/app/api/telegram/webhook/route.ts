import { NextResponse } from "next/server";
import { runAgent } from "@/lib/agent/run";
import { sendTelegram } from "@/lib/integrations/telegram";
import { sql, one } from "@/lib/db";

export const runtime = "nodejs";
export const maxDuration = 300;

/**
 * Two-way Telegram. Isaiah can message the bot and VERA answers with the same
 * tools and memory she has in the web app.
 *
 * Auth: Telegram echoes the secret_token we set at registration, and we hard-pin
 * the chat id so nobody else can talk to her even if they find the bot.
 */
export async function POST(req: Request) {
  const expected =
    process.env.TELEGRAM_WEBHOOK_SECRET || process.env.CRON_SECRET;
  const got = req.headers.get("x-telegram-bot-api-secret-token");
  if (!expected || got !== expected) {
    return NextResponse.json({ ok: true }); // stay quiet to strangers
  }

  let update: {
    message?: { text?: string; chat?: { id: number }; from?: { id: number } };
  };
  try {
    update = await req.json();
  } catch {
    return NextResponse.json({ ok: true });
  }

  const text = update.message?.text?.trim();
  const chatId = String(update.message?.chat?.id ?? "");
  if (!text) return NextResponse.json({ ok: true });

  if (chatId !== process.env.TELEGRAM_CHAT_ID) {
    return NextResponse.json({ ok: true });
  }

  // /brief and /status are handled without a model call.
  if (text === "/start" || text === "/help") {
    await sendTelegram(
      "*VERA* — One Vision Marketing\n\nAsk me anything about the business. I have your clients, revenue, inbox, tasks, and memory.\n\n`/brief` — today's briefing\n`/status` — quick numbers",
    );
    return NextResponse.json({ ok: true });
  }

  if (text === "/status") {
    const s = await one<{ active: number; risk: number; tasks: number; mail: number }>(
      `SELECT
        (SELECT count(*) FROM clients WHERE status='active')::int AS active,
        (SELECT count(*) FROM clients WHERE health_score<60 AND status='active')::int AS risk,
        (SELECT count(*) FROM tasks WHERE status IN ('open','doing'))::int AS tasks,
        (SELECT count(*) FROM emails WHERE needs_reply=true)::int AS mail`,
    );
    await sendTelegram(
      `📊 *Status*\n\nClients: ${s?.active ?? 0} active${s?.risk ? ` (${s.risk} at risk)` : ""}\nOpen tasks: ${s?.tasks ?? 0}\nEmails needing reply: ${s?.mail ?? 0}`,
    );
    return NextResponse.json({ ok: true });
  }

  const prompt = text === "/brief" ? "Give me my briefing right now." : text;

  // Reuse today's Telegram conversation so context carries between messages.
  const existing = await one<{ id: string }>(
    `SELECT id FROM conversations
      WHERE channel='telegram' AND updated_at > now() - interval '6 hours'
      ORDER BY updated_at DESC LIMIT 1`,
  );

  try {
    const { text: reply } = await runAgent({
      message: prompt,
      conversationId: existing?.id,
      channel: "telegram",
      maxTokens: 3000,
      systemOverride:
        "You are replying over Telegram. Keep it under 200 words. Plain sentences, minimal formatting — no headers, no tables. Lead with the answer.",
    });
    await sendTelegram(reply);
  } catch (err) {
    console.error("[telegram] agent error:", err);
    await sendTelegram("Something broke on my end. Try again in a minute.");
  }

  return NextResponse.json({ ok: true });
}

/** Convenience: GET registers the webhook when hit by a signed-in browser. */
export async function GET(req: Request) {
  const url = new URL(req.url);
  if (url.searchParams.get("secret") !== process.env.CRON_SECRET) {
    return NextResponse.json({ error: "Unauthorized" }, { status: 401 });
  }
  const { setTelegramWebhook } = await import("@/lib/integrations/telegram");
  const base = `${url.protocol}//${url.host}`;
  const ok = await setTelegramWebhook(base);
  return NextResponse.json({ registered: ok, url: `${base}/api/telegram/webhook` });
}
