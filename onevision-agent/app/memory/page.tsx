import { redirect } from "next/navigation";
import { revalidatePath } from "next/cache";
import { isAuthed } from "@/lib/auth";
import { sql } from "@/lib/db";
import { remember } from "@/lib/agent/memory";
import { ago } from "@/lib/format";

export const dynamic = "force-dynamic";

async function addFact(formData: FormData) {
  "use server";
  const content = String(formData.get("content") ?? "").trim();
  if (!content) return;
  await remember({
    content,
    kind: String(formData.get("kind") ?? "fact"),
    subject: String(formData.get("subject") ?? "") || undefined,
    importance: Number(formData.get("importance") ?? 3),
    source: "manual",
  });
  revalidatePath("/memory");
}

async function forgetFact(formData: FormData) {
  "use server";
  await sql(`UPDATE memory SET active=false WHERE id=$1`, [String(formData.get("id"))]);
  revalidatePath("/memory");
}

export default async function MemoryPage({
  searchParams,
}: { searchParams: Promise<{ q?: string }> }) {
  if (!(await isAuthed())) redirect("/login");
  const { q } = await searchParams;

  const rows = q?.trim()
    ? await sql<{ id: string; kind: string; subject: string | null; content: string;
                  importance: number; hit_count: number; source: string | null;
                  created_at: string; client: string | null }>(
        `SELECT m.id,m.kind,m.subject,m.content,m.importance,m.hit_count,m.source,
                m.created_at,c.name AS client
           FROM memory m LEFT JOIN clients c ON c.id=m.client_id
          WHERE m.active=true
            AND (m.search_vec @@ websearch_to_tsquery('english',$1)
                 OR m.content ILIKE $2 OR m.subject ILIKE $2)
          ORDER BY m.importance DESC, m.hit_count DESC LIMIT 100`,
        [q, `%${q}%`])
    : await sql<{ id: string; kind: string; subject: string | null; content: string;
                  importance: number; hit_count: number; source: string | null;
                  created_at: string; client: string | null }>(
        `SELECT m.id,m.kind,m.subject,m.content,m.importance,m.hit_count,m.source,
                m.created_at,c.name AS client
           FROM memory m LEFT JOIN clients c ON c.id=m.client_id
          WHERE m.active=true
          ORDER BY m.importance DESC, m.updated_at DESC LIMIT 100`);

  const [stats] = await sql<{ total: number; kinds: number }>(
    `SELECT count(*)::int AS total, count(DISTINCT kind)::int AS kinds
       FROM memory WHERE active=true`);

  return (
    <>
      <div className="topbar">
        <div>
          <h1>Memory</h1>
          <div className="sub">
            {stats.total} facts across {stats.kinds} categories · this is what VERA knows
          </div>
        </div>
      </div>
      <div className="content">
        <div className="card card-pad" style={{ marginBottom: 16 }}>
          <form style={{ display: "flex", gap: 10 }}>
            <input name="q" defaultValue={q ?? ""} placeholder="Search memory…" style={{ flex: 1 }} />
            <button className="btn ghost">Search</button>
          </form>
        </div>

        <div className="card card-pad" style={{ marginBottom: 20 }}>
          <form action={addFact} style={{ display: "flex", gap: 10, flexWrap: "wrap" }}>
            <input name="content" placeholder="Teach VERA something…" style={{ flex: "1 1 320px" }} required />
            <input name="subject" placeholder="Subject" style={{ width: 150 }} />
            <select name="kind" defaultValue="fact" style={{ width: 130 }}>
              {["fact","preference","decision","lesson","process","person","metric","risk"].map((k) => (
                <option key={k} value={k}>{k}</option>
              ))}
            </select>
            <select name="importance" defaultValue="3" style={{ width: 100 }}>
              {[5,4,3,2,1].map((i) => <option key={i} value={i}>★ {i}</option>)}
            </select>
            <button className="btn">Store</button>
          </form>
        </div>

        <div className="card">
          {rows.length ? (
            <table>
              <thead>
                <tr>
                  <th style={{ width: 92 }}>Kind</th>
                  <th style={{ width: 130 }}>Subject</th>
                  <th>Fact</th>
                  <th style={{ width: 62 }}>Used</th>
                  <th style={{ width: 80 }}></th>
                </tr>
              </thead>
              <tbody>
                {rows.map((m) => (
                  <tr key={m.id}>
                    <td><span className="pill neutral">{m.kind}</span></td>
                    <td className="muted">{m.subject ?? m.client ?? "—"}</td>
                    <td>
                      <div style={{ fontSize: 12.5 }}>{m.content}</div>
                      <div className="muted" style={{ fontSize: 11 }}>
                        {"★".repeat(m.importance)} · {m.source} · {ago(m.created_at)}
                      </div>
                    </td>
                    <td className="muted">{m.hit_count}×</td>
                    <td style={{ textAlign: "right" }}>
                      <form action={forgetFact}>
                        <input type="hidden" name="id" value={m.id} />
                        <button className="btn ghost sm">Forget</button>
                      </form>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          ) : (
            <div className="empty"><div className="big">◉</div>
              {q ? `Nothing matching "${q}"` : "Memory is empty"}
            </div>
          )}
        </div>
      </div>
    </>
  );
}
