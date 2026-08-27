import type Anthropic from "@anthropic-ai/sdk";

/**
 * Model provider abstraction.
 *
 * VERA's tool loop, memory, and jobs are provider-agnostic. Swap the backing
 * model by changing one environment variable:
 *
 *   LLM_PROVIDER=gemini      (default)  + GEMINI_API_KEY
 *   LLM_PROVIDER=anthropic              + ANTHROPIC_API_KEY
 *
 * Both implementations expose the same shape, so nothing downstream changes.
 */

// ---------------------------------------------------------------------------
// Neutral types
// ---------------------------------------------------------------------------

export interface ToolDef {
  name: string;
  description: string;
  input_schema: Record<string, unknown>;
}

export interface ToolCall {
  id: string;
  name: string;
  input: Record<string, unknown>;
}

export type ConvMessage =
  | { role: "user"; text: string }
  | { role: "assistant"; text: string; toolCalls?: ToolCall[] }
  | { role: "tool"; results: { id: string; name: string; output: string }[] };

export interface LLMResponse {
  text: string;
  toolCalls: ToolCall[];
  usage: { input: number; output: number; cacheRead: number };
  stop: "end" | "tool_use" | "refusal" | "other";
}

export interface GenerateRequest {
  /** Stable persona. Cached where the provider supports it. */
  system: string;
  /** Volatile business snapshot. Kept separate so it never poisons a cache prefix. */
  liveContext: string;
  messages: ConvMessage[];
  tools: ToolDef[];
  maxTokens: number;
}

export interface LLMProvider {
  readonly id: "gemini" | "anthropic";
  readonly model: string;
  generate(req: GenerateRequest): Promise<LLMResponse>;
}

// ---------------------------------------------------------------------------
// Gemini
// ---------------------------------------------------------------------------

const DEFAULT_GEMINI_MODEL = process.env.GEMINI_MODEL || "gemini-3.7-flash";

class GeminiProvider implements LLMProvider {
  readonly id = "gemini" as const;
  readonly model = DEFAULT_GEMINI_MODEL;

  async generate(req: GenerateRequest): Promise<LLMResponse> {
    const key = process.env.GEMINI_API_KEY || process.env.GOOGLE_API_KEY;
    if (!key) {
      throw new Error(
        "GEMINI_API_KEY is not set. Get one free at aistudio.google.com/apikey and add it in Vercel → Settings → Environment Variables.",
      );
    }

    const { GoogleGenAI } = await import("@google/genai");
    const ai = new GoogleGenAI({ apiKey: key });

    // Gemini does implicit context caching on repeated prefixes, so putting the
    // stable persona first still earns a discount — there is just no explicit
    // breakpoint to set the way Anthropic has.
    const systemInstruction = `${req.system}\n\n---\n\n${req.liveContext}`;

    const contents = req.messages.flatMap((m) => {
      if (m.role === "user") {
        return [{ role: "user", parts: [{ text: m.text }] }];
      }
      if (m.role === "assistant") {
        const parts: Record<string, unknown>[] = [];
        if (m.text) parts.push({ text: m.text });
        for (const tc of m.toolCalls ?? []) {
          parts.push({ functionCall: { name: tc.name, args: tc.input } });
        }
        return parts.length ? [{ role: "model", parts }] : [];
      }
      // Tool results go back as a user turn of functionResponse parts.
      return [
        {
          role: "user",
          parts: m.results.map((r) => ({
            functionResponse: {
              name: r.name,
              response: { result: r.output },
            },
          })),
        },
      ];
    });

    const res = await ai.models.generateContent({
      model: this.model,
      contents,
      config: {
        systemInstruction,
        maxOutputTokens: req.maxTokens,
        tools: [
          {
            functionDeclarations: req.tools.map((t) => ({
              name: t.name,
              description: t.description,
              parametersJsonSchema: t.input_schema,
            })),
          },
        ],
      },
    });

    const calls = res.functionCalls ?? [];
    const usage = res.usageMetadata;

    return {
      text: res.text ?? "",
      toolCalls: calls.map((c, i) => ({
        id: c.id ?? `call_${i}_${c.name}`,
        name: c.name ?? "",
        input: (c.args ?? {}) as Record<string, unknown>,
      })),
      usage: {
        input: usage?.promptTokenCount ?? 0,
        output: usage?.candidatesTokenCount ?? 0,
        cacheRead: usage?.cachedContentTokenCount ?? 0,
      },
      stop: calls.length ? "tool_use" : "end",
    };
  }
}

// ---------------------------------------------------------------------------
// Anthropic
// ---------------------------------------------------------------------------

const DEFAULT_ANTHROPIC_MODEL = process.env.ANTHROPIC_MODEL || "claude-opus-5";

class AnthropicProvider implements LLMProvider {
  readonly id = "anthropic" as const;
  readonly model = DEFAULT_ANTHROPIC_MODEL;

  async generate(req: GenerateRequest): Promise<LLMResponse> {
    if (!process.env.ANTHROPIC_API_KEY) {
      throw new Error("ANTHROPIC_API_KEY is not set.");
    }

    const { default: Anthropic } = await import("@anthropic-ai/sdk");
    const client = new Anthropic();

    const messages = req.messages.flatMap((m): Anthropic.MessageParam[] => {
      if (m.role === "user") return [{ role: "user", content: m.text }];
      if (m.role === "assistant") {
        const content: Anthropic.ContentBlockParam[] = [];
        if (m.text) content.push({ type: "text", text: m.text });
        for (const tc of m.toolCalls ?? []) {
          content.push({
            type: "tool_use",
            id: tc.id,
            name: tc.name,
            input: tc.input,
          });
        }
        return content.length ? [{ role: "assistant", content }] : [];
      }
      return [
        {
          role: "user",
          content: m.results.map((r) => ({
            type: "tool_result" as const,
            tool_use_id: r.id,
            content: r.output,
          })),
        },
      ];
    });

    const res = await client.messages.create({
      model: this.model,
      max_tokens: req.maxTokens,
      // Stable persona carries the cache breakpoint; volatile context sits
      // after it so it never invalidates the cached prefix.
      system: [
        {
          type: "text",
          text: req.system,
          cache_control: { type: "ephemeral" },
        },
        { type: "text", text: req.liveContext },
      ],
      tools: req.tools.map((t) => ({
        name: t.name,
        description: t.description,
        input_schema: t.input_schema as Anthropic.Tool["input_schema"],
      })),
      messages,
      ...({ output_config: { effort: "high" } } as Record<string, unknown>),
    });

    const toolCalls = res.content
      .filter((b): b is Anthropic.ToolUseBlock => b.type === "tool_use")
      .map((b) => ({
        id: b.id,
        name: b.name,
        input: b.input as Record<string, unknown>,
      }));

    return {
      text: res.content
        .filter((b): b is Anthropic.TextBlock => b.type === "text")
        .map((b) => b.text)
        .join("\n")
        .trim(),
      toolCalls,
      usage: {
        input: res.usage.input_tokens ?? 0,
        output: res.usage.output_tokens ?? 0,
        cacheRead: res.usage.cache_read_input_tokens ?? 0,
      },
      stop:
        res.stop_reason === "refusal"
          ? "refusal"
          : res.stop_reason === "tool_use"
            ? "tool_use"
            : res.stop_reason === "end_turn"
              ? "end"
              : "other",
    };
  }
}

// ---------------------------------------------------------------------------
// Factory
// ---------------------------------------------------------------------------

let cached: LLMProvider | null = null;

export function provider(): LLMProvider {
  if (cached) return cached;
  const choice = (process.env.LLM_PROVIDER || "gemini").toLowerCase();
  cached = choice === "anthropic" ? new AnthropicProvider() : new GeminiProvider();
  return cached;
}

/** Which provider is configured, and is its key present. Used by /api/health. */
export function providerStatus(): {
  id: string;
  model: string;
  keyEnv: string;
  keySet: boolean;
} {
  const choice = (process.env.LLM_PROVIDER || "gemini").toLowerCase();
  if (choice === "anthropic") {
    return {
      id: "anthropic",
      model: DEFAULT_ANTHROPIC_MODEL,
      keyEnv: "ANTHROPIC_API_KEY",
      keySet: Boolean(process.env.ANTHROPIC_API_KEY),
    };
  }
  return {
    id: "gemini",
    model: DEFAULT_GEMINI_MODEL,
    keyEnv: "GEMINI_API_KEY",
    keySet: Boolean(process.env.GEMINI_API_KEY || process.env.GOOGLE_API_KEY),
  };
}
