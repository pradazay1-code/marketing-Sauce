import { redirect } from "next/navigation";
import Link from "next/link";
import { isAuthed } from "@/lib/auth";
import { sql, isInitialized } from "@/lib/db";
import SetupNotice from "./components/SetupNotice";

export const dynamic = "force-dynamic";

const usd = (n: number) =>
  `$${n.toLocaleString("en-US", { maximumFractionDigits: 0 })}`;

function healthColor(score: number) {
  if (score >= 80) return "var(--green)";
  if (score >= 60) return "var(--amber)";
  return "var(--red)";
}

function ago(ts: string | null): string {
  if (!ts) return "never";
  const d = Math.floor((Date.now() - new Date(ts).getTime()) / 86_400_000);
  if (d === 0) return "today";
  if (d === 1) return "yesterday";
  if (d < 30) return `${d}d ago`;
  return `${Math.floor(d / 30)}mo ago`;
}

export default async function Dashboard() {
  if (!(await isAuthed())) redirect("/login");
  if (!(await isInitialized())) return <SetupNotice />;

  const [stats] = await sql<{
    active: number; at_risk: number; mrr: string;
    open_tasks: number; urgent_tasks: number; needs_reply: number;
    rev30: string; rev_prior: string; failed: number;
  }>(`
    SELECT
      (SELECT count(*) FROM clients WHERE status='active')::int AS active,
      (SELECT count(*) FROM clients WHERE health_score < 60
         AND status IN ('active','onboarding','paused'))::int AS at_risk,
      (SELECT COALESCE(SUM(monthly_value),0) FROM clients WHERE status='active')::text AS mrr,
      (SELECT count(*) FROM tasks WHERE status IN ('open','doing'))::int AS open_tasks,
      (SELECT count(*) FROM tasks WHERE status IN ('open','doing') AND priority='urgent')::int AS urgent_tasks,
      (SELECT count(*) FROM emails WHERE needs_reply = true)::int AS needs_reply,
      (SELECT COALESCE(SUM(amount_cents),0) FROM revenue_events
         WHERE type IN ('payment','invoice_paid') AND status <> 'failed'
           AND occurred_at > now() - interval '30 days')::text AS rev30,
      (SELECT COALESCE(SUM(amount_cents),0) FROM revenue_events
         WHERE type IN ('payment','invoice_paid') AND status <> 'failed'
           AND occurred_at > now() - interval '60 days'
           AND occurred_at <= now() - interval '30 days')::text AS rev_prior,
      (SELECT count(*) FROM revenue_events
         WHERE status='failed' AND occurred_at > now() - interval '30 days')::int AS failed
  `);

  const [clients, alerts, tasks, lastBrief] = await Promise.all([
    sql<{
      slug: string; name: string; status: string; health_score: number;
      health_notes: string | null; last_contact_at: string | null;
    }>(
      `SELECT slug, name, status, health_score, health_notes, last_contact_at
         FROM clients WHERE status IN ('active','onboarding','paused')
        ORDER BY health_score ASC LIMIT 8`,
    ),
    sql<{ id: string; severity: string; title: string; body: string | null; created_at: string }>(
      `SELECT id, severity, title, body, created_at FROM alerts
        WHERE acknowledged = false AND category <> 'system'
        ORDER BY created_at DESC LIMIT 6`,
    ),
    sql<{ id: string; title: string; priority: string; due_at: string | null; client: string | null }>(
      `SELECT t.id, t.title, t.priority, t.due_at, c.name AS client
         FROM tasks t LEFT JOIN clients c ON c.id = t.client_id
        WHERE t.status IN ('open','doing')
        ORDER BY CASE t.priority WHEN 'urgent' THEN 0 WHEN 'high' THEN 1
                                 WHEN 'normal' THEN 2 ELSE 3 END,
                 t.due_at NULLS LAST
        LIMIT 6`,
    ),
    sql<{ body: string | null; created_at: string }>(
      `SELECT body, created_at FROM alerts
        WHERE category='system' AND title LIKE 'Morning brief%'
        ORDER BY created_at DESC LIMIT 1`,
    ),
  ]);

  const rev30 = Number(stats.rev30) / 100;
  const revPrior = Number(stats.rev_prior) / 100;
  const delta = revPrior > 0 ? ((rev30 - revPrior) / revPrior) * 100 : 0;

  return (
    <>
      <div className="topbar">
        <div>
          <h1>Dashboard</h1>
          <div className="sub">
            {new Date().toLocaleDateString("en-US", {
              weekday: "long", month: "long", day: "numeric",
            })}
          </div>
        </div>
        <Link href="/chat" className="btn">
          Ask VERA
        </Link>
      </div>

      <div className="content">
        {/* ---- stats ---- */}
        <div className="grid g4" style={{ marginBottom: 20 }}>
          <div className="card card-pad stat">
            <div className="k">Active clients</div>
            <div className="v">{stats.active}</div>
            <div className={`d ${stats.at_risk > 0 ? "down" : ""}`}>
              {stats.at_risk > 0 ? `${stats.at_risk} at risk` : "all healthy"}
            </div>
          </div>
          <div className="card card-pad stat">
            <div className="k">Contracted MRR</div>
            <div className="v">{usd(Number(stats.mrr))}</div>
            <div className="d">recurring</div>
          </div>
          <div className="card card-pad stat">
            <div className="k">Collected · 30d</div>
            <div className="v">{usd(rev30)}</div>
            <div className={`d ${delta >= 0 ? "up" : "down"}`}>
              {revPrior > 0
                ? `${delta >= 0 ? "▲" : "▼"} ${Math.abs(delta).toFixed(0)}% vs prior 30d`
                : "no prior period"}
            </div>
          </div>
          <div className="card card-pad stat">
            <div className="k">Needs you</div>
            <div className="v">{stats.needs_reply + stats.open_tasks}</div>
            <div className={`d ${stats.urgent_tasks > 0 ? "down" : ""}`}>
              {stats.needs_reply} emails · {stats.open_tasks} tasks
            </div>
          </div>
        </div>

        {/* ---- morning brief ---- */}
        {lastBrief[0]?.body && (
          <div className="card" style={{ marginBottom: 20 }}>
            <div className="card-head">
              <h2>Latest brief from VERA</h2>
              <span className="hint">{ago(lastBrief[0].created_at)}</span>
            </div>
            <div className="card-pad" style={{ whiteSpace: "pre-wrap", fontSize: 13.5, lineHeight: 1.7 }}>
              {lastBrief[0].body}
            </div>
          </div>
        )}

        <div className="grid g2">
          {/* ---- client health ---- */}
          <div className="card">
            <div className="card-head">
              <h2>Client health</h2>
              <Link href="/clients" className="hint">View all →</Link>
            </div>
            {clients.length ? (
              <table>
                <tbody>
                  {clients.map((c) => (
                    <tr key={c.slug}>
                      <td>
                        <Link href={`/clients/${c.slug}`} style={{ fontWeight: 600, color: "var(--navy)" }}>
                          {c.name}
                        </Link>
                        <div className="muted" style={{ fontSize: 11.5 }}>
                          last contact {ago(c.last_contact_at)}
                        </div>
                      </td>
                      <td style={{ width: 110 }}>
                        <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
                          <div className="health-bar">
                            <span style={{
                              width: `${c.health_score}%`,
                              background: healthColor(c.health_score),
                            }} />
                          </div>
                          <span style={{ fontSize: 12, fontWeight: 700, color: healthColor(c.health_score) }}>
                            {c.health_score}
                          </span>
                        </div>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            ) : (
              <div className="empty"><div className="big">◐</div>No clients yet</div>
            )}
          </div>

          {/* ---- alerts ---- */}
          <div className="card">
            <div className="card-head">
              <h2>Open alerts</h2>
              <Link href="/alerts" className="hint">View all →</Link>
            </div>
            {alerts.length ? (
              <div>
                {alerts.map((a) => (
                  <div key={a.id} className="feed-item">
                    <div className={`feed-dot ${a.severity}`} />
                    <div className="feed-body">
                      <div className="t">{a.title}</div>
                      {a.body && (
                        <div className="b">
                          {a.body.length > 160 ? a.body.slice(0, 160) + "…" : a.body}
                        </div>
                      )}
                      <div className="m">{ago(a.created_at)}</div>
                    </div>
                  </div>
                ))}
              </div>
            ) : (
              <div className="empty"><div className="big">✓</div>Nothing flagged</div>
            )}
          </div>
        </div>

        {/* ---- tasks ---- */}
        <div className="card" style={{ marginTop: 20 }}>
          <div className="card-head">
            <h2>What needs doing</h2>
            <Link href="/tasks" className="hint">View all →</Link>
          </div>
          {tasks.length ? (
            <table>
              <tbody>
                {tasks.map((t) => (
                  <tr key={t.id}>
                    <td>
                      <span className={`pill ${
                        t.priority === "urgent" ? "bad"
                        : t.priority === "high" ? "warn" : "neutral"
                      }`}>{t.priority}</span>
                    </td>
                    <td style={{ fontWeight: 500 }}>{t.title}</td>
                    <td className="muted">{t.client ?? "—"}</td>
                    <td className="muted" style={{ textAlign: "right" }}>
                      {t.due_at ? new Date(t.due_at).toLocaleDateString("en-US", { month: "short", day: "numeric" }) : ""}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          ) : (
            <div className="empty"><div className="big">✓</div>Nothing open</div>
          )}
        </div>
      </div>
    </>
  );
}
