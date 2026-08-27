import { sql, one } from "../db";
import { CORE_PERSONA, buildLiveContext, type LiveContext } from "./persona";
import { TOOLS, executeTool } from "./tools";
import { recall } from "./memory";
import { provider, type ConvMessage, type ToolCall } from "./provider";

const MAX_TOOL_ITERATIONS = 12;

export interface RunResult {
  text: string;
  toolCalls: { name: string; input: unknown }[];
  usage: { input: number; output: number; cacheRead: number };
  conversationId: string;
  model: string;
}

/**
 * Assemble the live business snapshot injected on every turn.
 * Cheap aggregate queries — all indexed, all bounded.
 */
async function gatherContext(query: string): Promise<LiveContext> {
  const [clientAgg, atRisk, taskAgg, inboxAgg, revAgg, alerts, memories] =
    await Promise.all([
      one<{ active: number; mrr: string }>(
        `SELECT count(*) FILTER (WHERE status='active')::int AS active,
                COALESCE(SUM(monthly_value) FILTER (WHERE status='active'),0)::text AS mrr
           FROM clients`,
      ),
      sql<{ name: string; health_score: number; health_notes: string | null }>(
        `SELECT name, health_score, health_notes FROM clients
          WHERE health_score < 60 AND status IN ('active','onboarding','paused')
          ORDER BY health_score ASC LIMIT 8`,
      ),
      one<{ open: number; urgent: number }>(
        `SELECT count(*)::int AS open,
                count(*) FILTER (WHERE priority='urgent')::int AS urgent
           FROM tasks WHERE status IN ('open','doing')`,
      ),
      one<{ n: number }>(
        `SELECT count(*)::int AS n FROM emails WHERE needs_reply = true`,
      ),
      one<{ cents: string }>(
        `SELECT COALESCE(SUM(amount_cents),0)::text AS cents
           FROM revenue_events
          WHERE type IN ('payment','invoice_paid')
            AND status IS DISTINCT FROM 'failed'
            AND occurred_at > now() - interval '30 days'`,
      ),
      sql<{ severity: string; title: string }>(
        `SELECT severity, title FROM alerts
          WHERE acknowledged = false ORDER BY created_at DESC LIMIT 6`,
      ),
      recall(query, 10),
    ]);

  return {
    now: new Date().toLocaleString("en-US", {
      timeZone: "America/New_York",
      dateStyle: "full",
      timeStyle: "short",
    }),
    activeClients: clientAgg?.active ?? 0,
    mrrCents: Math.round(Number(clientAgg?.mrr ?? 0) * 100),
    last30Cents: Number(revAgg?.cents ?? 0),
    openTasks: taskAgg?.open ?? 0,
    urgentTasks: taskAgg?.urgent ?? 0,
    unreadNeedingReply: inboxAgg?.n ?? 0,
    atRiskClients: atRisk.map(
      (c) =>
        `${c.name} — health ${c.health_score}${c.health_notes ? ` (${c.health_notes})` : ""}`,
    ),
    recentAlerts: alerts.map((a) => `[${a.severity}] ${a.title}`),
    relevantMemory: memories.map((m) =>
      m.subject ? `${m.subject}: ${m.content}` : m.content,
    ),
  };
}

/**
 * Run one turn of the agent, including the full tool loop.
 *
 * Provider-agnostic: the persona and live context are passed separately so each
 * provider can place its own cache boundary between them.
 */
export async function runAgent(opts: {
  message: string;
  conversationId?: string;
  channel?: "web" | "telegram" | "cron";
  systemOverride?: string;
  maxTokens?: number;
}): Promise<RunResult> {
  const { message, channel = "web", systemOverride } = opts;
  const llm = provider();

  // --- conversation ---
  let conversationId = opts.conversationId ?? "";
  if (!conversationId) {
    const conv = await one<{ id: string }>(
      `INSERT INTO conversations (title, channel) VALUES ($1,$2) RETURNING id`,
      [message.slice(0, 80), channel],
    );
    conversationId = conv!.id;
  }

  const history = await sql<{ role: string; content: string }>(
    `SELECT role, content FROM messages
      WHERE conversation_id = $1 AND role IN ('user','assistant')
      ORDER BY created_at ASC LIMIT 40`,
    [conversationId],
  );

  const messages: ConvMessage[] = history.map((m) =>
    m.role === "user"
      ? { role: "user", text: m.content }
      : { role: "assistant", text: m.content },
  );
  messages.push({ role: "user", text: message });

  await sql(
    `INSERT INTO messages (conversation_id, role, content) VALUES ($1,'user',$2)`,
    [conversationId, message],
  );

  const ctx = await gatherContext(message);
  const system = systemOverride
    ? `${CORE_PERSONA}\n\n${systemOverride}`
    : CORE_PERSONA;
  const liveContext = buildLiveContext(ctx);

  // --- tool loop ---
  const allCalls: RunResult["toolCalls"] = [];
  const usage = { input: 0, output: 0, cacheRead: 0 };
  let finalText = "";

  for (let i = 0; i < MAX_TOOL_ITERATIONS; i++) {
    const res = await llm.generate({
      system,
      liveContext,
      messages,
      tools: TOOLS,
      maxTokens: opts.maxTokens ?? 8000,
    });

    usage.input += res.usage.input;
    usage.output += res.usage.output;
    usage.cacheRead += res.usage.cacheRead;

    if (res.text) finalText = res.text;

    if (res.stop === "refusal") {
      finalText =
        "I stopped short on that one — it tripped a safety filter. Rephrase it and I will take another look.";
      break;
    }

    if (!res.toolCalls.length) break;

    messages.push({
      role: "assistant",
      text: res.text,
      toolCalls: res.toolCalls,
    });

    // Tools are independent — run them concurrently and return every result
    // together, so the model keeps making parallel calls.
    const results = await Promise.all(
      res.toolCalls.map(async (tc: ToolCall) => {
        allCalls.push({ name: tc.name, input: tc.input });
        const output = await executeTool(tc.name, tc.input);
        return { id: tc.id, name: tc.name, output: output.slice(0, 60_000) };
      }),
    );

    messages.push({ role: "tool", results });
  }

  if (!finalText) {
    finalText =
      "I hit my tool limit before landing on an answer. Narrow the question and I will retry.";
  }

  await sql(
    `INSERT INTO messages
       (conversation_id, role, content, tool_calls, tokens_in, tokens_out, cache_read)
     VALUES ($1,'assistant',$2,$3,$4,$5,$6)`,
    [
      conversationId,
      finalText,
      allCalls.length ? JSON.stringify(allCalls) : null,
      usage.input,
      usage.output,
      usage.cacheRead,
    ],
  );
  await sql(`UPDATE conversations SET updated_at = now() WHERE id = $1`, [
    conversationId,
  ]);

  return {
    text: finalText,
    toolCalls: allCalls,
    usage,
    conversationId,
    model: llm.model,
  };
}
