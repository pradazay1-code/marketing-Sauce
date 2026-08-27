import { redirect } from "next/navigation";
import { isAuthed } from "@/lib/auth";
import { sql } from "@/lib/db";
import { usd, usdc, dateShort } from "@/lib/format";

export const dynamic = "force-dynamic";

export default async function RevenuePage() {
  if (!(await isAuthed())) redirect("/login");

  const [agg] = await sql<{
    r30: string; r60: string; r365: string; failed: string; failed_n: number; mrr: string;
  }>(
    `SELECT
      COALESCE(SUM(amount_cents) FILTER (WHERE type IN ('payment','invoice_paid')
        AND status<>'failed' AND occurred_at > now()-interval '30 days'),0)::text AS r30,
      COALESCE(SUM(amount_cents) FILTER (WHERE type IN ('payment','invoice_paid')
        AND status<>'failed' AND occurred_at > now()-interval '60 days'
        AND occurred_at <= now()-interval '30 days'),0)::text AS r60,
      COALESCE(SUM(amount_cents) FILTER (WHERE type IN ('payment','invoice_paid')
        AND status<>'failed' AND occurred_at > now()-interval '365 days'),0)::text AS r365,
      COALESCE(SUM(amount_cents) FILTER (WHERE status='failed'
        AND occurred_at > now()-interval '30 days'),0)::text AS failed,
      count(*) FILTER (WHERE status='failed' AND occurred_at > now()-interval '30 days')::int AS failed_n,
      (SELECT COALESCE(SUM(monthly_value),0) FROM clients WHERE status='active')::text AS mrr
     FROM revenue_events`,
  );

  const [byClient, months, recent] = await Promise.all([
    sql<{ client: string; usd: number; events: number }>(
      `SELECT COALESCE(c.name, r.customer_email, 'Unattributed') AS client,
              (SUM(r.amount_cents)/100.0)::float AS usd, count(*)::int AS events
         FROM revenue_events r LEFT JOIN clients c ON c.id = r.client_id
        WHERE r.type IN ('payment','invoice_paid') AND r.status <> 'failed'
          AND r.occurred_at > now() - interval '365 days'
        GROUP BY 1 ORDER BY 2 DESC LIMIT 15`),
    sql<{ month: string; usd: number }>(
      `SELECT to_char(date_trunc('month', occurred_at), 'Mon YYYY') AS month,
              (SUM(amount_cents)/100.0)::float AS usd
         FROM revenue_events
        WHERE type IN ('payment','invoice_paid') AND status <> 'failed'
          AND occurred_at > now() - interval '12 months'
        GROUP BY date_trunc('month', occurred_at)
        ORDER BY date_trunc('month', occurred_at) DESC LIMIT 12`),
    sql<{ occurred_at: string; type: string; amount_cents: string; status: string | null;
          customer_email: string | null; description: string | null; client: string | null }>(
      `SELECT r.occurred_at, r.type, r.amount_cents, r.status, r.customer_email,
              r.description, c.name AS client
         FROM revenue_events r LEFT JOIN clients c ON c.id = r.client_id
        ORDER BY r.occurred_at DESC LIMIT 30`),
  ]);

  const r30 = Number(agg.r30) / 100;
  const r60 = Number(agg.r60) / 100;
  const delta = r60 > 0 ? ((r30 - r60) / r60) * 100 : 0;
  const peak = Math.max(...months.map((m) => m.usd), 1);

  return (
    <>
      <div className="topbar">
        <div>
          <h1>Revenue</h1>
          <div className="sub">Mirrored from Stripe · synced every 2 hours</div>
        </div>
      </div>
      <div className="content">
        <div className="grid g4" style={{ marginBottom: 20 }}>
          <div className="card card-pad stat">
            <div className="k">Last 30 days</div><div className="v">{usd(r30)}</div>
            <div className={`d ${delta >= 0 ? "up" : "down"}`}>
              {r60 > 0 ? `${delta >= 0 ? "▲" : "▼"} ${Math.abs(delta).toFixed(0)}% vs prior` : "no prior period"}
            </div>
          </div>
          <div className="card card-pad stat">
            <div className="k">Contracted MRR</div><div className="v">{usd(Number(agg.mrr))}</div>
            <div className="d">from active clients</div>
          </div>
          <div className="card card-pad stat">
            <div className="k">Trailing 12 months</div><div className="v">{usdc(agg.r365)}</div>
            <div className="d">collected</div>
          </div>
          <div className="card card-pad stat">
            <div className="k">Failed · 30d</div>
            <div className="v" style={{ color: agg.failed_n > 0 ? "var(--red)" : undefined }}>
              {usdc(agg.failed)}
            </div>
            <div className={`d ${agg.failed_n > 0 ? "down" : ""}`}>
              {agg.failed_n} failed charge{agg.failed_n === 1 ? "" : "s"}
            </div>
          </div>
        </div>

        {months.length > 0 && (
          <div className="card" style={{ marginBottom: 20 }}>
            <div className="card-head"><h2>Monthly collected</h2></div>
            <div className="card-pad">
              {months.map((m) => (
                <div key={m.month} style={{ display: "flex", alignItems: "center", gap: 12, marginBottom: 7 }}>
                  <span className="muted" style={{ width: 74, fontSize: 11.5 }}>{m.month}</span>
                  <div style={{ flex: 1, height: 20, background: "var(--bg)", borderRadius: 4, overflow: "hidden" }}>
                    <div style={{ width: `${(m.usd / peak) * 100}%`, height: "100%",
                                  background: "var(--navy-mid)", borderRadius: 4 }} />
                  </div>
                  <span style={{ width: 74, textAlign: "right", fontSize: 12, fontWeight: 700 }}>
                    {usd(m.usd)}
                  </span>
                </div>
              ))}
            </div>
          </div>
        )}

        <div className="grid g2">
          <div className="card">
            <div className="card-head"><h2>By client · 12 months</h2></div>
            {byClient.length ? (
              <table><tbody>
                {byClient.map((b, i) => (
                  <tr key={i}>
                    <td style={{ fontWeight: 500 }}>{b.client}</td>
                    <td className="muted" style={{ width: 60 }}>{b.events}×</td>
                    <td style={{ textAlign: "right", fontWeight: 700 }}>{usd(b.usd)}</td>
                  </tr>
                ))}
              </tbody></table>
            ) : <div className="empty">No revenue recorded</div>}
          </div>

          <div className="card">
            <div className="card-head"><h2>Recent transactions</h2></div>
            {recent.length ? (
              <table><tbody>
                {recent.map((r, i) => (
                  <tr key={i}>
                    <td className="muted" style={{ width: 62 }}>{dateShort(r.occurred_at)}</td>
                    <td>
                      <div style={{ fontSize: 12.5 }}>{r.client ?? r.customer_email ?? r.description ?? r.type}</div>
                      <div className="muted" style={{ fontSize: 11 }}>{r.type.replace(/_/g, " ")}</div>
                    </td>
                    <td style={{ textAlign: "right", fontWeight: 700,
                        color: r.status === "failed" ? "var(--red)"
                             : r.type === "refund" ? "var(--amber)" : "var(--green)" }}>
                      {r.type === "refund" ? "−" : ""}{usdc(r.amount_cents)}
                    </td>
                  </tr>
                ))}
              </tbody></table>
            ) : (
              <div className="empty">
                <div className="big">$</div>
                No Stripe data.<br />
                <span style={{ fontSize: 12 }}>Add STRIPE_SECRET_KEY, then run the sync job.</span>
              </div>
            )}
          </div>
        </div>
      </div>
    </>
  );
}
