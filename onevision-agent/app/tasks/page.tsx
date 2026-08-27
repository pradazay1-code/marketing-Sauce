import { redirect } from "next/navigation";
import { revalidatePath } from "next/cache";
import { isAuthed } from "@/lib/auth";
import { sql } from "@/lib/db";
import { dateShort, ago } from "@/lib/format";

export const dynamic = "force-dynamic";

async function complete(formData: FormData) {
  "use server";
  const id = String(formData.get("id"));
  await sql(
    `UPDATE tasks SET status='done', completed_at=now() WHERE id=$1`, [id]);
  revalidatePath("/tasks");
}

async function add(formData: FormData) {
  "use server";
  const title = String(formData.get("title") ?? "").trim();
  if (!title) return;
  await sql(
    `INSERT INTO tasks (title, priority, due_at, source) VALUES ($1,$2,$3,'isaiah')`,
    [title, String(formData.get("priority") ?? "normal"),
     String(formData.get("due_at") ?? "") || null],
  );
  revalidatePath("/tasks");
}

export default async function TasksPage() {
  if (!(await isAuthed())) redirect("/login");

  const [open, done] = await Promise.all([
    sql<{ id: string; title: string; detail: string | null; priority: string;
          due_at: string | null; client: string | null; source: string | null; created_at: string }>(
      `SELECT t.id,t.title,t.detail,t.priority,t.due_at,c.name AS client,t.source,t.created_at
         FROM tasks t LEFT JOIN clients c ON c.id=t.client_id
        WHERE t.status IN ('open','doing')
        ORDER BY CASE t.priority WHEN 'urgent' THEN 0 WHEN 'high' THEN 1
                                 WHEN 'normal' THEN 2 ELSE 3 END, t.due_at NULLS LAST`),
    sql<{ id: string; title: string; completed_at: string }>(
      `SELECT id,title,completed_at FROM tasks WHERE status='done'
        ORDER BY completed_at DESC LIMIT 12`),
  ]);

  return (
    <>
      <div className="topbar">
        <div>
          <h1>Tasks</h1>
          <div className="sub">{open.length} open · VERA adds these when she spots something</div>
        </div>
      </div>
      <div className="content">
        <div className="card card-pad" style={{ marginBottom: 20 }}>
          <form action={add} style={{ display: "flex", gap: 10, flexWrap: "wrap" }}>
            <input name="title" placeholder="Add a task…" style={{ flex: "1 1 280px" }} required />
            <select name="priority" defaultValue="normal" style={{ width: 120 }}>
              <option value="urgent">Urgent</option>
              <option value="high">High</option>
              <option value="normal">Normal</option>
              <option value="low">Low</option>
            </select>
            <input type="date" name="due_at" style={{ width: 150 }} />
            <button className="btn">Add</button>
          </form>
        </div>

        <div className="card">
          <div className="card-head"><h2>Open</h2></div>
          {open.length ? (
            <table><tbody>
              {open.map((t) => (
                <tr key={t.id}>
                  <td style={{ width: 74 }}>
                    <span className={`pill ${
                      t.priority === "urgent" ? "bad" : t.priority === "high" ? "warn" : "neutral"}`}>
                      {t.priority}
                    </span>
                  </td>
                  <td>
                    <div style={{ fontWeight: 500 }}>{t.title}</div>
                    {t.detail && <div className="muted" style={{ fontSize: 11.5 }}>{t.detail}</div>}
                    <div className="muted" style={{ fontSize: 11 }}>
                      {t.source === "agent" ? "flagged by VERA" : "added by you"} · {ago(t.created_at)}
                    </div>
                  </td>
                  <td className="muted">{t.client ?? ""}</td>
                  <td className="muted" style={{ width: 80 }}>
                    {t.due_at ? dateShort(t.due_at) : ""}
                  </td>
                  <td style={{ width: 90, textAlign: "right" }}>
                    <form action={complete}>
                      <input type="hidden" name="id" value={t.id} />
                      <button className="btn ghost sm">Done</button>
                    </form>
                  </td>
                </tr>
              ))}
            </tbody></table>
          ) : <div className="empty"><div className="big">✓</div>Nothing open</div>}
        </div>

        {done.length > 0 && (
          <div className="card" style={{ marginTop: 20 }}>
            <div className="card-head"><h2>Recently completed</h2></div>
            <table><tbody>
              {done.map((t) => (
                <tr key={t.id}>
                  <td className="muted" style={{ textDecoration: "line-through" }}>{t.title}</td>
                  <td className="muted" style={{ textAlign: "right", width: 90 }}>{ago(t.completed_at)}</td>
                </tr>
              ))}
            </tbody></table>
          </div>
        )}
      </div>
    </>
  );
}
