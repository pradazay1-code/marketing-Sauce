import { redirect } from "next/navigation";
import Link from "next/link";
import { isAuthed } from "@/lib/auth";
import { sql } from "@/lib/db";
import { ago, healthColor, usd } from "@/lib/format";

export const dynamic = "force-dynamic";

export default async function ClientsPage() {
  if (!(await isAuthed())) redirect("/login");

  const clients = await sql<{
    slug: string; name: string; contact_name: string | null; industry: string | null;
    city: string | null; state: string | null; status: string; monthly_value: string | null;
    health_score: number; health_notes: string | null; last_contact_at: string | null;
    deliverables: number; overdue: number;
  }>(
    `SELECT c.slug, c.name, c.contact_name, c.industry, c.city, c.state, c.status,
            c.monthly_value, c.health_score, c.health_notes, c.last_contact_at,
            (SELECT count(*) FROM deliverables d WHERE d.client_id=c.id)::int AS deliverables,
            (SELECT count(*) FROM deliverables d WHERE d.client_id=c.id
               AND d.due_at < CURRENT_DATE AND d.status NOT IN ('delivered','cancelled'))::int AS overdue
       FROM clients c
      ORDER BY
        CASE c.status WHEN 'active' THEN 0 WHEN 'onboarding' THEN 1
                      WHEN 'paused' THEN 2 WHEN 'prospect' THEN 3 ELSE 4 END,
        c.health_score ASC`,
  );

  return (
    <>
      <div className="topbar">
        <div>
          <h1>Clients</h1>
          <div className="sub">{clients.length} total · VERA reviews health every Monday</div>
        </div>
      </div>
      <div className="content">
        <div className="card">
          {clients.length ? (
            <table>
              <thead>
                <tr>
                  <th>Client</th>
                  <th>Status</th>
                  <th>Health</th>
                  <th>Work</th>
                  <th>Value</th>
                  <th style={{ textAlign: "right" }}>Last contact</th>
                </tr>
              </thead>
              <tbody>
                {clients.map((c) => (
                  <tr key={c.slug}>
                    <td>
                      <Link href={`/clients/${c.slug}`} style={{ fontWeight: 600, color: "var(--navy)" }}>
                        {c.name}
                      </Link>
                      <div className="muted" style={{ fontSize: 11.5 }}>
                        {[c.contact_name, c.industry, [c.city, c.state].filter(Boolean).join(", ")]
                          .filter(Boolean).join(" · ") || "—"}
                      </div>
                    </td>
                    <td>
                      <span className={`pill ${
                        c.status === "active" ? "ok"
                        : c.status === "churned" ? "bad"
                        : c.status === "paused" ? "warn" : "neutral"}`}>
                        {c.status}
                      </span>
                    </td>
                    <td>
                      <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
                        <div className="health-bar">
                          <span style={{ width: `${c.health_score}%`, background: healthColor(c.health_score) }} />
                        </div>
                        <span style={{ fontSize: 12, fontWeight: 700, color: healthColor(c.health_score) }}>
                          {c.health_score}
                        </span>
                      </div>
                      {c.health_notes && (
                        <div className="muted" style={{ fontSize: 11, marginTop: 3 }}>{c.health_notes}</div>
                      )}
                    </td>
                    <td className="muted">
                      {c.deliverables} item{c.deliverables === 1 ? "" : "s"}
                      {c.overdue > 0 && (
                        <span className="pill bad" style={{ marginLeft: 6 }}>{c.overdue} late</span>
                      )}
                    </td>
                    <td className="muted">
                      {Number(c.monthly_value) > 0 ? `${usd(Number(c.monthly_value))}/mo` : "—"}
                    </td>
                    <td className="muted" style={{ textAlign: "right" }}>{ago(c.last_contact_at)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          ) : (
            <div className="empty"><div className="big">◐</div>No clients yet</div>
          )}
        </div>
      </div>
    </>
  );
}
