import { redirect } from "next/navigation";
import { revalidatePath } from "next/cache";
import { isAuthed } from "@/lib/auth";
import { sql } from "@/lib/db";
import { ago } from "@/lib/format";

export const dynamic = "force-dynamic";

async function ack(formData: FormData) {
  "use server";
  await sql(`UPDATE alerts SET acknowledged=true WHERE id=$1`, [String(formData.get("id"))]);
  revalidatePath("/alerts");
}

async function ackAll() {
  "use server";
  await sql(`UPDATE alerts SET acknowledged=true WHERE acknowledged=false`);
  revalidatePath("/alerts");
}

export default async function AlertsPage() {
  if (!(await isAuthed())) redirect("/login");

  const alerts = await sql<{
    id: string; severity: string; title: string; body: string | null;
    category: string | null; acknowledged: boolean; sent_telegram: boolean;
    created_at: string; client: string | null;
  }>(
    `SELECT a.id,a.severity,a.title,a.body,a.category,a.acknowledged,
            a.sent_telegram,a.created_at,c.name AS client
       FROM alerts a LEFT JOIN clients c ON c.id=a.client_id
      ORDER BY a.acknowledged ASC, a.created_at DESC LIMIT 60`,
  );

  const open = alerts.filter((a) => !a.acknowledged).length;

  return (
    <>
      <div className="topbar">
        <div>
          <h1>Alerts</h1>
          <div className="sub">{open} unacknowledged</div>
        </div>
        {open > 0 && (
          <form action={ackAll}>
            <button className="btn ghost sm">Acknowledge all</button>
          </form>
        )}
      </div>
      <div className="content">
        <div className="card">
          {alerts.length ? (
            <div>
              {alerts.map((a) => (
                <div key={a.id} className="feed-item"
                     style={{ opacity: a.acknowledged ? 0.5 : 1 }}>
                  <div className={`feed-dot ${a.severity}`} />
                  <div className="feed-body">
                    <div className="t">{a.title}</div>
                    {a.body && <div className="b">{a.body}</div>}
                    <div className="m">
                      {[a.category, a.client, ago(a.created_at),
                        a.sent_telegram ? "sent to Telegram" : null]
                        .filter(Boolean).join(" · ")}
                    </div>
                  </div>
                  {!a.acknowledged && (
                    <form action={ack}>
                      <input type="hidden" name="id" value={a.id} />
                      <button className="btn ghost sm">Dismiss</button>
                    </form>
                  )}
                </div>
              ))}
            </div>
          ) : (
            <div className="empty"><div className="big">✓</div>Nothing flagged</div>
          )}
        </div>
      </div>
    </>
  );
}
