/**
 * Telegram — outbound alerts to Isaiah's phone.
 *
 * Setup:
 *   1. Message @BotFather on Telegram, send /newbot, follow prompts.
 *   2. Copy the bot token → TELEGRAM_BOT_TOKEN
 *   3. Message your new bot once (say "hi"), then open:
 *      https://api.telegram.org/bot<TOKEN>/getUpdates
 *      Find "chat":{"id":123456789} → TELEGRAM_CHAT_ID
 */

const API = "https://api.telegram.org";

export function telegramConfigured(): boolean {
  return Boolean(process.env.TELEGRAM_BOT_TOKEN && process.env.TELEGRAM_CHAT_ID);
}

/** Send a message. Returns false rather than throwing — alerts must never break a job. */
export async function sendTelegram(
  text: string,
  opts: { silent?: boolean } = {},
): Promise<boolean> {
  const token = process.env.TELEGRAM_BOT_TOKEN;
  const chatId = process.env.TELEGRAM_CHAT_ID;
  if (!token || !chatId) return false;

  try {
    const res = await fetch(`${API}/bot${token}/sendMessage`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        chat_id: chatId,
        text: truncate(text, 4000),
        parse_mode: "Markdown",
        disable_notification: opts.silent ?? false,
        link_preview_options: { is_disabled: true },
      }),
    });

    if (res.ok) return true;

    // Markdown parse failures are the common case — retry as plain text so the
    // alert still lands.
    const body = await res.text();
    if (body.includes("can't parse entities")) {
      const retry = await fetch(`${API}/bot${token}/sendMessage`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          chat_id: chatId,
          text: truncate(stripMarkdown(text), 4000),
          disable_notification: opts.silent ?? false,
        }),
      });
      return retry.ok;
    }

    console.error("[telegram] send failed:", body.slice(0, 300));
    return false;
  } catch (err) {
    console.error("[telegram] network error:", err);
    return false;
  }
}

/** Register the webhook so Isaiah can chat with VERA from Telegram. */
export async function setTelegramWebhook(publicUrl: string): Promise<boolean> {
  const token = process.env.TELEGRAM_BOT_TOKEN;
  if (!token) return false;
  const secret = process.env.TELEGRAM_WEBHOOK_SECRET || process.env.CRON_SECRET;
  const res = await fetch(`${API}/bot${token}/setWebhook`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      url: `${publicUrl.replace(/\/$/, "")}/api/telegram/webhook`,
      secret_token: secret,
      allowed_updates: ["message"],
    }),
  });
  return res.ok;
}

function truncate(s: string, n: number): string {
  return s.length <= n ? s : s.slice(0, n - 20) + "\n\n…(truncated)";
}

function stripMarkdown(s: string): string {
  return s.replace(/[*_`[\]()~>#+=|{}!-]/g, "");
}
