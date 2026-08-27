"use client";

import { useState, useRef, useEffect } from "react";

interface Turn {
  role: "user" | "vera";
  text: string;
  tools?: string[];
}

const SUGGESTIONS = [
  "What needs my attention today?",
  "How is Akira Real Estate doing?",
  "What did I collect this month vs last?",
  "Which clients have gone quiet?",
  "What's sitting in my inbox that matters?",
];

export default function ChatPage() {
  const [turns, setTurns] = useState<Turn[]>([]);
  const [input, setInput] = useState("");
  const [busy, setBusy] = useState(false);
  const [convId, setConvId] = useState<string | undefined>();
  const logRef = useRef<HTMLDivElement>(null);
  const taRef = useRef<HTMLTextAreaElement>(null);

  useEffect(() => {
    logRef.current?.scrollTo({ top: logRef.current.scrollHeight, behavior: "smooth" });
  }, [turns, busy]);

  async function send(text: string) {
    const msg = text.trim();
    if (!msg || busy) return;

    setTurns((t) => [...t, { role: "user", text: msg }]);
    setInput("");
    setBusy(true);
    if (taRef.current) taRef.current.style.height = "auto";

    try {
      const res = await fetch("/api/chat", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ message: msg, conversationId: convId }),
      });

      if (!res.ok) {
        const err = await res.json().catch(() => ({ error: "Request failed" }));
        setTurns((t) => [
          ...t,
          { role: "vera", text: `⚠ ${err.error ?? `HTTP ${res.status}`}` },
        ]);
        return;
      }

      const data = (await res.json()) as {
        text: string;
        conversationId: string;
        toolCalls?: { name: string }[];
      };
      setConvId(data.conversationId);
      setTurns((t) => [
        ...t,
        {
          role: "vera",
          text: data.text,
          tools: [...new Set((data.toolCalls ?? []).map((c) => c.name))],
        },
      ]);
    } catch {
      setTurns((t) => [
        ...t,
        { role: "vera", text: "⚠ Network error — could not reach the server." },
      ]);
    } finally {
      setBusy(false);
      taRef.current?.focus();
    }
  }

  return (
    <>
      <div className="topbar">
        <div>
          <h1>Ask VERA</h1>
          <div className="sub">She has full access to your clients, revenue, inbox, and memory</div>
        </div>
        {turns.length > 0 && (
          <button
            className="btn ghost sm"
            onClick={() => { setTurns([]); setConvId(undefined); }}
          >
            New conversation
          </button>
        )}
      </div>

      <div className="chat-wrap">
        <div className="chat-log" ref={logRef}>
          {turns.length === 0 && !busy && (
            <div style={{ maxWidth: 620, margin: "60px auto 0", textAlign: "center" }}>
              <div style={{ fontSize: 34, fontWeight: 800, letterSpacing: 9, color: "var(--navy)" }}>
                VERA
              </div>
              <div style={{ width: 46, height: 2, background: "var(--accent)", borderRadius: 2, margin: "12px auto 10px" }} />
              <p className="muted" style={{ marginBottom: 30 }}>
                Fifteen years with One Vision. Ask her anything about the business.
              </p>
              <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
                {SUGGESTIONS.map((s) => (
                  <button
                    key={s}
                    className="btn ghost"
                    style={{ justifyContent: "flex-start", fontWeight: 500 }}
                    onClick={() => send(s)}
                  >
                    {s}
                  </button>
                ))}
              </div>
            </div>
          )}

          {turns.map((t, i) => (
            <div key={i} className={`turn ${t.role}`}>
              <div className="who">{t.role === "user" ? "Isaiah" : "VERA"}</div>
              <div className="bubble" dangerouslySetInnerHTML={{ __html: render(t.text) }} />
              {t.tools && t.tools.length > 0 && (
                <div className="tools-used">
                  {t.tools.map((n) => (
                    <span key={n}>{n}</span>
                  ))}
                </div>
              )}
            </div>
          ))}

          {busy && (
            <div className="turn vera">
              <div className="who">VERA</div>
              <div className="thinking"><i /><i /><i /></div>
            </div>
          )}
        </div>

        <div className="chat-input">
          <form
            onSubmit={(e) => { e.preventDefault(); send(input); }}
          >
            <textarea
              ref={taRef}
              value={input}
              placeholder="Ask about clients, revenue, inbox, anything…"
              disabled={busy}
              onChange={(e) => {
                setInput(e.target.value);
                e.target.style.height = "auto";
                e.target.style.height = Math.min(e.target.scrollHeight, 190) + "px";
              }}
              onKeyDown={(e) => {
                if (e.key === "Enter" && !e.shiftKey) {
                  e.preventDefault();
                  send(input);
                }
              }}
            />
            <button className="btn" disabled={busy || !input.trim()}>
              Send
            </button>
          </form>
        </div>
      </div>
    </>
  );
}

/**
 * Minimal markdown → HTML. Everything is escaped first, so model output can
 * never inject markup.
 */
function render(md: string): string {
  const esc = md
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;");

  const lines = esc.split("\n");
  const out: string[] = [];
  let list: "ul" | "ol" | null = null;

  const closeList = () => {
    if (list) { out.push(`</${list}>`); list = null; }
  };

  for (const raw of lines) {
    const line = raw.trimEnd();

    if (!line.trim()) { closeList(); continue; }

    const h = line.match(/^(#{1,4})\s+(.*)$/);
    if (h) { closeList(); out.push(`<h3>${inline(h[2])}</h3>`); continue; }

    const ul = line.match(/^\s*[-*•]\s+(.*)$/);
    if (ul) {
      if (list !== "ul") { closeList(); out.push("<ul>"); list = "ul"; }
      out.push(`<li>${inline(ul[1])}</li>`);
      continue;
    }

    const ol = line.match(/^\s*\d+[.)]\s+(.*)$/);
    if (ol) {
      if (list !== "ol") { closeList(); out.push("<ol>"); list = "ol"; }
      out.push(`<li>${inline(ol[1])}</li>`);
      continue;
    }

    closeList();
    out.push(`<p>${inline(line)}</p>`);
  }
  closeList();
  return out.join("");
}

function inline(s: string): string {
  return s
    .replace(/`([^`]+)`/g, "<code>$1</code>")
    .replace(/\*\*([^*]+)\*\*/g, "<strong>$1</strong>")
    .replace(/(^|[\s(])\*([^*\s][^*]*)\*/g, "$1<em>$2</em>");
}
