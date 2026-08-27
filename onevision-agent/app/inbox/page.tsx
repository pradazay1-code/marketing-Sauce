import { redirect } from "next/navigation";
import { isAuthed } from "@/lib/auth";
import { sql } from "@/lib/db";
import { ago } from "@/lib/format";

export const dynamic = "force-dynamic";

export default async function InboxPage() {
  if (!(await isAuthed())) redirect("/login");

  const emails = await sql<{
    id: string; from_name: string | null; from_email: string | null;
    subject: string | null; summary: string | null; snippet: string | null;
    priority: string | null; category: string | null; needs_reply: boolean;
    suggested_action: string | null; received_at: string; client: string | null;
  }>(
    `SELECT e.id, e.from_name, e.from_email, e.subject, e.summary, e.snippet,
            e.priority, e.category, e.needs_reply, e.suggested_action,
            e.received_at, c.name AS client
       FROM emails e LEFT JOIN clients c ON c.id = e.client_id
      WHERE e.received_at > now() - interval '21 days'
        AND COALESCE(e.priority,'normal') <> 'ignore'
      ORDER BY
        CASE e.priority WHEN 'urgent' THEN 0 WHEN 'high' THEN 1
                        WHEN 'normal' THEN 2 ELSE 3 END,
        e.received_at DESC
      LIMIT 80`,
  );

  const needsReply = emails.filter((e) => e.needs_reply).length;

  return (
    <>
      <div className="topbar">
        <div>
          <h1>Inbox</h1>
          <div className="sub">
            {emails.length} triaged · {needsReply} awaiting reply · synced every 2 hours
          </div>
        </div>
      </div>
      <div className="content">
        <div className="card">
          {emails.length ? (
            <table>
              <thead>
                <tr>
                  <th style={{ width: 74 }}>Priority</th>
                  <th>From</th>
                  <th>Subject &amp; VERA&apos;s read</th>
                  <th style={{ width: 80, textAlign: "right" }}>Received</th>
                </tr>
              </thead>
              <tbody>
                {emails.map((e) => (
                  <tr key={e.id}>
                    <td>
                      <span className={`pill ${
                        e.priority === "urgent" ? "bad"
                        : e.priority === "high" ? "warn"
                        : e.priority === "low" ? "neutral" : "neutral"}`}>
                        {e.priority ?? "—"}
                      </span>
                    </td>
                    <td>
                      <div style={{ fontWeight: 600, fontSize: 12.5 }}>
                        {e.from_name ?? e.from_email ?? "unknown"}
                      </div>
                      <div className="muted" style={{ fontSize: 11 }}>
                        {e.client ? `↳ ${e.client}` : e.category ?? ""}
                      </div>
                    </td>
                    <td>
                      <div style={{ fontWeight: 500 }}>{e.subject ?? "(no subject)"}</div>
                      <div className="muted" style={{ fontSize: 11.5, marginTop: 2 }}>
                        {e.summary ?? e.snippet ?? ""}
                      </div>
                      {e.needs_reply && e.suggested_action && (
                        <div style={{ fontSize: 11.5, marginTop: 4, color: "var(--navy-mid)", fontWeight: 500 }}>
                          → {e.suggested_action}
                        </div>
                      )}
                    </td>
                    <td className="muted" style={{ textAlign: "right" }}>{ago(e.received_at)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          ) : (
            <div className="empty">
              <div className="big">✉</div>
              No email synced yet.<br />
              <span style={{ fontSize: 12 }}>Connect Gmail in Settings, then run the sync job.</span>
            </div>
          )}
        </div>
      </div>
    </>
  );
}
