import { redirect } from "next/navigation";
import { isAuthed } from "@/lib/auth";
import { sql } from "@/lib/db";
import { gmailStatus, gmailConfigured } from "@/lib/integrations/gmail";
import { stripeConfigured } from "@/lib/integrations/stripe";
import { telegramConfigured } from "@/lib/integrations/telegram";
import { ago } from "@/lib/format";
import { providerStatus } from "@/lib/agent/provider";
import RunJobs from "../components/RunJobs";

export const dynamic = "force-dynamic";

const NOTICES: Record<string, { text: string; ok: boolean }> = {
  connected: { text: "Gmail connected.", ok: true },
  denied: { text: "Google access was denied.", ok: false },
  nocode: { text: "Google returned no authorization code.", ok: false },
  badstate: { text: "State check failed — start the connection again.", ok: false },
  failed: { text: "Token exchange failed. Check your client ID and secret.", ok: false },
};

export default async function SettingsPage({
  searchParams,
}: {
  searchParams: Promise<{ gmail?: string }>;
}) {
  if (!(await isAuthed())) redirect("/login");
  const { gmail: notice } = await searchParams;

  const [gmail, jobs] = await Promise.all([
    gmailStatus().catch(() => ({ connected: false, email: null })),
    sql<{ job: string; status: string; detail: string | null; started_at: string }>(
      `SELECT DISTINCT ON (job) job, status, detail, started_at
         FROM job_runs ORDER BY job, started_at DESC`,
    ).catch(() => []),
  ]);

  const jobMap = Object.fromEntries(jobs.map((j) => [j.job, j]));

  const prov = providerStatus();

  const rows = [
    {
      name: prov.id === "gemini" ? "Google Gemini" : "Anthropic",
      need: prov.keyEnv,
      on: prov.keySet,
      detail: `Model: ${prov.model}`,
      required: true,
    },
    {
      name: "Postgres",
      need: "DATABASE_URL",
      on: Boolean(process.env.DATABASE_URL),
      detail: "Clients, memory, revenue, email, tasks",
      required: true,
    },
    {
      name: "Telegram",
      need: "TELEGRAM_BOT_TOKEN + TELEGRAM_CHAT_ID",
      on: telegramConfigured(),
      detail: "Push alerts and two-way chat",
      required: false,
    },
    {
      name: "Stripe",
      need: "STRIPE_SECRET_KEY",
      on: stripeConfigured(),
      detail: "Revenue mirroring (read-only)",
      required: false,
    },
  ];

  return (
    <>
      <div className="topbar">
        <div>
          <h1>Settings</h1>
          <div className="sub">Connections and scheduled jobs</div>
        </div>
      </div>

      <div className="content">
        {notice && NOTICES[notice] && (
          <div
            className="card card-pad"
            style={{
              marginBottom: 18,
              background: NOTICES[notice].ok ? "var(--green-bg)" : "var(--red-bg)",
              borderColor: NOTICES[notice].ok ? "var(--green)" : "var(--red)",
              color: NOTICES[notice].ok ? "var(--green)" : "var(--red)",
              fontSize: 13,
              fontWeight: 600,
            }}
          >
            {NOTICES[notice].text}
          </div>
        )}

        {/* ---- connections ---- */}
        <div className="card" style={{ marginBottom: 20 }}>
          <div className="card-head">
            <h2>Connections</h2>
            <span className="hint">Set these in Vercel → Settings → Environment Variables</span>
          </div>
          <table>
            <tbody>
              {rows.map((r) => (
                <tr key={r.name}>
                  <td style={{ width: 130, fontWeight: 600 }}>{r.name}</td>
                  <td>
                    <span className={`pill ${r.on ? "ok" : r.required ? "bad" : "neutral"}`}>
                      {r.on ? "connected" : r.required ? "missing" : "not set"}
                    </span>
                  </td>
                  <td className="muted">{r.detail}</td>
                  <td className="mono muted" style={{ textAlign: "right", fontSize: 11 }}>
                    {r.need}
                  </td>
                </tr>
              ))}

              {/* Gmail is OAuth, so it gets its own row with a button */}
              <tr>
                <td style={{ fontWeight: 600 }}>Gmail</td>
                <td>
                  <span className={`pill ${gmail.connected ? "ok" : "neutral"}`}>
                    {gmail.connected ? "connected" : "not connected"}
                  </span>
                </td>
                <td className="muted">
                  {gmail.connected
                    ? `Reading ${gmail.email ?? "your inbox"} (read-only)`
                    : gmailConfigured()
                      ? "Ready to connect"
                      : "Set GOOGLE_CLIENT_ID and GOOGLE_CLIENT_SECRET first"}
                </td>
                <td style={{ textAlign: "right" }}>
                  {gmailConfigured() && (
                    <a href="/api/oauth/google/start" className="btn ghost sm">
                      {gmail.connected ? "Reconnect" : "Connect Gmail"}
                    </a>
                  )}
                </td>
              </tr>
            </tbody>
          </table>
        </div>

        {/* ---- jobs ---- */}
        <div className="card" style={{ marginBottom: 20 }}>
          <div className="card-head">
            <h2>Scheduled jobs</h2>
            <span className="hint">Times are UTC in vercel.json</span>
          </div>
          <table>
            <thead>
              <tr>
                <th>Job</th>
                <th>Runs</th>
                <th>Last result</th>
                <th style={{ textAlign: "right" }}>Manual</th>
              </tr>
            </thead>
            <tbody>
              {[
                { id: "sync", label: "Sync Gmail + Stripe", when: "Every 2 hours" },
                { id: "watchdog", label: "Watchdog rules", when: "Hourly" },
                { id: "morning-brief", label: "Morning brief", when: "Daily 7:30am ET" },
                { id: "client-review", label: "Client health review", when: "Mondays 9am ET" },
              ].map((j) => {
                const last = jobMap[j.id];
                return (
                  <tr key={j.id}>
                    <td style={{ fontWeight: 600 }}>{j.label}</td>
                    <td className="muted">{j.when}</td>
                    <td>
                      {last ? (
                        <>
                          <span className={`pill ${last.status === "ok" ? "ok" : last.status === "error" ? "bad" : "neutral"}`}>
                            {last.status}
                          </span>
                          <div className="muted" style={{ fontSize: 11, marginTop: 3 }}>
                            {ago(last.started_at)} · {last.detail ?? ""}
                          </div>
                        </>
                      ) : (
                        <span className="muted">never run</span>
                      )}
                    </td>
                    <td style={{ textAlign: "right" }}>
                      <RunJobs job={j.id} />
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>

        {/* ---- telegram setup help ---- */}
        {telegramConfigured() && (
          <div className="card card-pad">
            <h2 style={{ fontSize: 14, fontWeight: 700, color: "var(--navy)", marginBottom: 8 }}>
              Two-way Telegram
            </h2>
            <p className="muted" style={{ marginBottom: 10 }}>
              Alerts already push to your phone. To also chat with VERA from Telegram,
              register the webhook once by visiting this URL in your browser:
            </p>
            <pre
              className="mono"
              style={{
                background: "var(--surface-2)",
                border: "1px solid var(--border)",
                borderRadius: 7,
                padding: "10px 12px",
                overflowX: "auto",
                fontSize: 11.5,
              }}
            >
{`/api/telegram/webhook?secret=<YOUR_CRON_SECRET>`}
            </pre>
            <p className="muted" style={{ marginTop: 10 }}>
              Then message your bot. <code className="mono">/brief</code> and{" "}
              <code className="mono">/status</code> work as shortcuts.
            </p>
          </div>
        )}
      </div>
    </>
  );
}
