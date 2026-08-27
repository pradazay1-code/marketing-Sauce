import Anthropic from "@anthropic-ai/sdk";
import { sql, one } from "../db";
import { CORE_PERSONA, buildLiveContext, type LiveContext } from "./persona";
import { TOOLS, executeTool } from "./tools";
import { recall } from "./memory";

const MODEL = process.env.AGENT_MODEL || "claude-opus-5";
const MAX_TOOL_ITERATIONS = 12;

let _client: Anthropic | null = null;
function client(): Anthropic {
  if (!_client) {
    if (!process.env.ANTHROPIC_API_KEY) {
      throw new Error(
        "ANTHROPIC_API_KEY is not set. Add it in Vercel → Settings → Environment Variables.",
      );
    }
    _client = new Anthropic();
  }
  return _client;
}

export interface RunResult {
  text: string;
  toolCalls: { name: string; input: unknown }[];
  usage: {
    input: number;
    output: number;
    cacheRead: number;
    cacheWrite: number;
  };
  conversationId: string;
}

/**
 * Assemble the live business snapshot injected on every turn.
 * Cheap aggregate queries — all indexed, all bounded.
 */
async function gatherContext(query: string): Promise<LiveContext> {
  const [
    clientAgg,
    atRisk,
    taskAgg,
    inboxAgg,
    revAgg,
    alerts,
    memories,
  ] = await Promise.all([
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
    sql<{ severity: string; title: string; created_at: string }>(
      `SELECT severity, title, created_at FROM alerts
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
      (c) => `${c.name} — health ${c.health_score}${c.health_notes ? ` (${c.health_notes})` : ""}`,
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
 * Prompt caching layout — order matters:
 *   tools           (frozen array)
 *   system[0]       CORE_PERSONA        <- cache breakpoint here
 *   system[1]       live business state  (volatile, after the breakpoint)
 *   messages        conversation history
 *
 * Everything up to and including system[0] is a stable prefix, so it is billed
 * at ~10% on every turn after the first.
 */
export async function runAgent(opts: {
  message: string;
  conversationId?: string;
  channel?: "web" | "telegram" | "cron";
  systemOverride?: string;
  maxTokens?: number;
}): Promise<RunResult> {
  const { message, channel = "web", systemOverride } = opts;

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

  const messages: Anthropic.MessageParam[] = history.map((m) => ({
    role: m.role as "user" | "assistant",
    content: m.content,
  }));
  messages.push({ role: "user", content: message });

  await sql(
    `INSERT INTO messages (conversation_id, role, content) VALUES ($1,'user',$2)`,
    [conversationId, message],
  );

  // --- system blocks ---
  const ctx = await gatherContext(message);
  const system: Anthropic.TextBlockParam[] = [
    {
      type: "text",
      text: systemOverride ? `${CORE_PERSONA}\n\n${systemOverride}` : CORE_PERSONA,
      cache_control: { type: "ephemeral" },
    },
    { type: "text", text: buildLiveContext(ctx) },
  ];

  // --- tool loop ---
  const toolCalls: RunResult["toolCalls"] = [];
  const usage = { input: 0, output: 0, cacheRead: 0, cacheWrite: 0 };
  let finalText = "";

  for (let i = 0; i < MAX_TOOL_ITERATIONS; i++) {
    // Thinking is on by default on Opus 5 — omitting the param runs adaptive.
    // `effort` is passed through as an extra body field because the installed
    // SDK version predates the typed `output_config`.
    const response = await client().messages.create({
      model: MODEL,
      max_tokens: opts.maxTokens ?? 8000,
      system,
      tools: TOOLS,
      messages,
      ...({ output_config: { effort: "high" } } as Record<string, unknown>),
    });

    usage.input += response.usage.input_tokens ?? 0;
    usage.output += response.usage.output_tokens ?? 0;
    usage.cacheRead += response.usage.cache_read_input_tokens ?? 0;
    usage.cacheWrite += response.usage.cache_creation_input_tokens ?? 0;

    if (response.stop_reason === "refusal") {
      finalText =
        "I stopped short on that one — it tripped a safety check. Rephrase it and I will take another look.";
      break;
    }

    const text = response.content
      .filter((b): b is Anthropic.TextBlock => b.type === "text")
      .map((b) => b.text)
      .join("\n")
      .trim();
    if (text) finalText = text;

    if (response.stop_reason !== "tool_use") break;

    const toolUses = response.content.filter(
      (b): b is Anthropic.ToolUseBlock => b.type === "tool_use",
    );
    if (!toolUses.length) break;

    messages.push({ role: "assistant", content: response.content });

    // Tools are independent — run them concurrently, return every result in
    // ONE user message. Splitting them trains the model out of parallel calls.
    const results = await Promise.all(
      toolUses.map(async (tu) => {
        toolCalls.push({ name: tu.name, input: tu.input });
        const out = await executeTool(tu.name, tu.input as Record<string, unknown>);
        const block: Anthropic.ToolResultBlockParam = {
          type: "tool_result",
          tool_use_id: tu.id,
          content: out.slice(0, 60_000),
          is_error: out.startsWith('{"error"'),
        };
        return block;
      }),
    );

    messages.push({ role: "user", content: results });
  }

  if (!finalText) {
    finalText = "I hit my tool limit before landing on an answer. Narrow the question and I will retry.";
  }

  await sql(
    `INSERT INTO messages
       (conversation_id, role, content, tool_calls, tokens_in, tokens_out, cache_read)
     VALUES ($1,'assistant',$2,$3,$4,$5,$6)`,
    [
      conversationId,
      finalText,
      toolCalls.length ? JSON.stringify(toolCalls) : null,
      usage.input,
      usage.output,
      usage.cacheRead,
    ],
  );
  await sql(`UPDATE conversations SET updated_at = now() WHERE id = $1`, [
    conversationId,
  ]);

  return { text: finalText, toolCalls, usage, conversationId };
}
