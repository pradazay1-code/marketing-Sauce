export default function SetupNotice() {
  return (
    <>
      <div className="topbar">
        <div>
          <h1>Setup required</h1>
          <div className="sub">The database schema has not been applied yet</div>
        </div>
      </div>
      <div className="content">
        <div className="card card-pad" style={{ maxWidth: 640 }}>
          <p style={{ fontSize: 13.5, marginBottom: 14 }}>
            VERA is connected but her tables do not exist. Apply the schema once and
            this screen goes away.
          </p>
          <p className="muted" style={{ marginBottom: 6 }}>
            From your machine, with <code className="mono">DATABASE_URL</code> set:
          </p>
          <pre
            className="mono"
            style={{
              background: "var(--surface-2)",
              border: "1px solid var(--border)",
              borderRadius: 7,
              padding: "12px 14px",
              overflowX: "auto",
            }}
          >
{`psql "$DATABASE_URL" -f db/schema.sql`}
          </pre>
          <p className="muted" style={{ marginTop: 14 }}>
            Or paste the contents of <code className="mono">db/schema.sql</code> into
            the SQL editor in Neon, Supabase, or the Vercel Postgres console. It is
            safe to run more than once.
          </p>
        </div>
      </div>
    </>
  );
}
