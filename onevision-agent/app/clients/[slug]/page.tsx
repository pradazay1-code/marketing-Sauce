import { redirect, notFound } from "next/navigation";
import Link from "next/link";
import { isAuthed } from "@/lib/auth";
import { sql, one, type Client } from "@/lib/db";
import { ago, healthColor, usd, usdc, dateShort } from "@/lib/format";

export const dynamic = "force-dynamic";

export default async function ClientDetail({
  params,
}: { params: Promise<{ slug: string }> }) {
  if (!(await isAuthed())) redirect("/login");
  const { slug } = await params;

  const client = await one<Client>(`SELECT * FROM clients WHERE slug = $1`, [slug]);
  if (!client) notFound();

  const [deliverables, revenue, emails, memories] = await Promise.all([
    sql<{ id: string; title: string; kind: string; status: string; detail: string | null;
          url: string | null; due_at: string | null; delivered_at: string | null }>(
      `SELECT id,title,kind,status,detail,url,due_at,delivered_at FROM deliverables
        WHERE client_id=$1 ORDER BY COALESCE(delivered_at,due_at,created_at) DESC`, [client.id]),
    sql<{ type: string; amount_cents: string; status: string | null; occurred_at: string; description: string | null }>(
      `SELECT type,amount_cents,status,occurred_at,description FROM revenue_events
        WHERE client_id=$1 ORDER BY occurred_at DESC LIMIT 15`, [client.id]),
    sql<{ subject: string | null; from_email: string | null; received_at: string; priority: string | null; summary: string | null }>(
      `SELECT subject,from_email,received_at,priority,summary FROM emails
        WHERE client_id=$1 ORDER BY received_at DESC LIMIT 10`, [client.id]),
    sql<{ content: string; kind: string; importance: number; created_at: string }>(
      `SELECT content,kind,importance,created_at FROM memory
        WHERE client_id=$1 AND active=true ORDER BY importance DESC, updated_at DESC LIMIT 20`, [client.id]),
  ]);

  return (
    <>
      <div className="topbar">
        <div>
          <h1>{client.name}</h1>
          <div className="sub">
            {[client.contact_name, client.industry,
              [client.city, client.state].filter(Boolean).join(", ")]
              .filter(Boolean).join(" · ")}
          </div>
        </div>
        <Link href="/clients" className="btn ghost sm">← All clients</Link>
      </div>

      <div className="content">
        <div className="grid g4" style={{ marginBottom: 20 }}>
          <div className="card card-pad stat">
            <div className="k">Health</div>
            <div className="v" style={{ color: healthColor(client.health_score) }}>{client.health_score}</div>
            <div className="d">{client.health_notes ?? "not yet reviewed"}</div>
          </div>
          <div className="card card-pad stat">
            <div className="k">Status</div>
            <div className="v" style={{ fontSize: 20, textTransform: "capitalize" }}>{client.status}</div>
            <div className="d">since {client.started_at ? dateShort(client.started_at) : "—"}</div>
          </div>
          <div className="card card-pad stat">
            <div className="k">Monthly value</div>
            <div className="v">{Number(client.monthly_value) > 0 ? usd(Number(client.monthly_value)) : "—"}</div>
            <div className="d">recurring</div>
          </div>
          <div className="card card-pad stat">
            <div className="k">Last contact</div>
            <div className="v" style={{ fontSize: 20 }}>{ago(client.last_contact_at)}</div>
            <div className="d">reviewed {ago(client.last_reviewed_at)}</div>
          </div>
        </div>

        <div className="grid g2">
          <div className="card">
            <div className="card-head"><h2>Deliverables</h2><span className="hint">{deliverables.length}</span></div>
            {deliverables.length ? (
              <table><tbody>
                {deliverables.map((d) => (
                  <tr key={d.id}>
                    <td>
                      <div style={{ fontWeight: 600 }}>{d.title}</div>
                      {d.detail && <div className="muted" style={{ fontSize: 11.5 }}>{d.detail}</div>}
                    </td>
                    <td style={{ width: 110 }}>
                      <span className={`pill ${
                        d.status === "delivered" ? "ok"
                        : d.status === "blocked" ? "bad"
                        : d.status === "in_progress" ? "warn" : "neutral"}`}>
                        {d.status.replace("_", " ")}
                      </span>
                    </td>
                    <td className="muted" style={{ width: 78, textAlign: "right" }}>
                      {d.delivered_at ? dateShort(d.delivered_at) : d.due_at ? `due ${dateShort(d.due_at)}` : ""}
                    </td>
                  </tr>
                ))}
              </tbody></table>
            ) : <div className="empty">No work logged</div>}
          </div>

          <div className="card">
            <div className="card-head"><h2>What VERA knows</h2><span className="hint">{memories.length} facts</span></div>
            {memories.length ? (
              <div>
                {memories.map((m, i) => (
                  <div key={i} className="feed-item">
                    <div className="feed-dot info" />
                    <div className="feed-body">
                      <div className="b" style={{ marginTop: 0 }}>{m.content}</div>
                      <div className="m">{m.kind} · {ago(m.created_at)}</div>
                    </div>
                  </div>
                ))}
              </div>
            ) : <div className="empty">Nothing recorded yet</div>}
          </div>
        </div>

        <div className="grid g2" style={{ marginTop: 20 }}>
          <div className="card">
            <div className="card-head"><h2>Revenue</h2></div>
            {revenue.length ? (
              <table><tbody>
                {revenue.map((r, i) => (
                  <tr key={i}>
                    <td className="muted">{dateShort(r.occurred_at)}</td>
                    <td>{r.description ?? r.type}</td>
                    <td style={{ textAlign: "right", fontWeight: 700,
                        color: r.status === "failed" ? "var(--red)" : "var(--green)" }}>
                      {usdc(r.amount_cents)}
                    </td>
                  </tr>
                ))}
              </tbody></table>
            ) : <div className="empty">No payments recorded</div>}
          </div>

          <div className="card">
            <div className="card-head"><h2>Recent email</h2></div>
            {emails.length ? (
              <table><tbody>
                {emails.map((e, i) => (
                  <tr key={i}>
                    <td>
                      <div style={{ fontWeight: 600, fontSize: 12.5 }}>{e.subject ?? "(no subject)"}</div>
                      <div className="muted" style={{ fontSize: 11.5 }}>{e.summary ?? e.from_email}</div>
                    </td>
                    <td className="muted" style={{ textAlign: "right", width: 74 }}>{ago(e.received_at)}</td>
                  </tr>
                ))}
              </tbody></table>
            ) : <div className="empty">No email linked</div>}
          </div>
        </div>

        {client.notes && (
          <div className="card" style={{ marginTop: 20 }}>
            <div className="card-head"><h2>Notes</h2></div>
            <div className="card-pad" style={{ fontSize: 13, whiteSpace: "pre-wrap" }}>{client.notes}</div>
          </div>
        )}
      </div>
    </>
  );
}
