import { sql, one } from "../db";

/**
 * Stripe — mirror charges, invoices, and subscription events into Postgres so
 * VERA can answer revenue questions without hitting the Stripe API every time.
 *
 * Read-only. Uses the REST API directly (no SDK dependency) — the surface we
 * need is three endpoints.
 *
 * Setup:
 *   dashboard.stripe.com → Developers → API keys → Secret key (sk_live_… / sk_test_…)
 *   → STRIPE_SECRET_KEY
 */

const API = "https://api.stripe.com/v1";

export function stripeConfigured(): boolean {
  return Boolean(process.env.STRIPE_SECRET_KEY);
}

async function stripeGet<T>(
  path: string,
  params: Record<string, string | number> = {},
): Promise<T | null> {
  const key = process.env.STRIPE_SECRET_KEY;
  if (!key) return null;

  const qs = new URLSearchParams(
    Object.entries(params).map(([k, v]) => [k, String(v)]),
  );
  try {
    const res = await fetch(`${API}${path}?${qs}`, {
      headers: {
        Authorization: `Bearer ${key}`,
        "Stripe-Version": "2024-06-20",
      },
    });
    if (!res.ok) {
      console.error(`[stripe] ${path} → ${res.status}`, (await res.text()).slice(0, 300));
      return null;
    }
    return (await res.json()) as T;
  } catch (err) {
    console.error(`[stripe] ${path} network error:`, err);
    return null;
  }
}

interface StripeCharge {
  id: string;
  amount: number;
  amount_refunded: number;
  currency: string;
  status: string;
  paid: boolean;
  created: number;
  description: string | null;
  failure_message: string | null;
  customer: string | null;
  billing_details?: { name?: string | null; email?: string | null };
  receipt_email?: string | null;
}

interface StripeSubscription {
  id: string;
  status: string;
  created: number;
  canceled_at: number | null;
  customer: string;
  items: { data: { price: { unit_amount: number | null; recurring?: { interval: string } } }[] };
}

interface StripeList<T> {
  data: T[];
  has_more: boolean;
}

/**
 * Pull recent Stripe activity. Idempotent — ON CONFLICT on stripe_id.
 * Returns how many new events landed.
 */
export async function syncStripe(opts: { days?: number } = {}): Promise<{
  charges: number;
  subscriptions: number;
}> {
  if (!stripeConfigured()) return { charges: 0, subscriptions: 0 };

  const days = opts.days ?? 45;
  const since = Math.floor(Date.now() / 1000) - days * 86_400;

  let charges = 0;
  let subs = 0;

  // ---- charges ----
  const chargeList = await stripeGet<StripeList<StripeCharge>>("/charges", {
    limit: 100,
    "created[gte]": since,
  });

  for (const ch of chargeList?.data ?? []) {
    const failed = !ch.paid || ch.status === "failed";
    const email = ch.billing_details?.email ?? ch.receipt_email ?? null;
    await sql(
      `INSERT INTO revenue_events
         (stripe_id, type, amount_cents, currency, status, customer_email,
          customer_name, stripe_customer_id, description, occurred_at, raw)
       VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,to_timestamp($10),$11)
       ON CONFLICT (stripe_id) DO UPDATE
         SET status = EXCLUDED.status, amount_cents = EXCLUDED.amount_cents`,
      [
        ch.id,
        failed ? "failed" : "payment",
        ch.amount,
        ch.currency,
        failed ? "failed" : ch.status,
        email,
        ch.billing_details?.name ?? null,
        typeof ch.customer === "string" ? ch.customer : null,
        ch.description ?? ch.failure_message ?? null,
        ch.created,
        JSON.stringify({ refunded: ch.amount_refunded }),
      ],
    );
    charges++;

    if (ch.amount_refunded > 0) {
      await sql(
        `INSERT INTO revenue_events
           (stripe_id, type, amount_cents, currency, status, customer_email,
            stripe_customer_id, description, occurred_at)
         VALUES ($1,'refund',$2,$3,'succeeded',$4,$5,$6,to_timestamp($7))
         ON CONFLICT (stripe_id) DO NOTHING`,
        [
          `${ch.id}_refund`,
          ch.amount_refunded,
          ch.currency,
          email,
          typeof ch.customer === "string" ? ch.customer : null,
          "Refund",
          ch.created,
        ],
      );
    }
  }

  // ---- subscriptions ----
  const subList = await stripeGet<StripeList<StripeSubscription>>("/subscriptions", {
    limit: 100,
    status: "all",
    "created[gte]": since,
  });

  for (const s of subList?.data ?? []) {
    const monthly = s.items.data.reduce((sum, it) => {
      const amt = it.price.unit_amount ?? 0;
      return sum + (it.price.recurring?.interval === "year" ? Math.round(amt / 12) : amt);
    }, 0);

    const cancelled = Boolean(s.canceled_at);
    await sql(
      `INSERT INTO revenue_events
         (stripe_id, type, amount_cents, currency, status, stripe_customer_id,
          description, occurred_at)
       VALUES ($1,$2,$3,'usd',$4,$5,$6,to_timestamp($7))
       ON CONFLICT (stripe_id) DO UPDATE SET status = EXCLUDED.status`,
      [
        cancelled ? `${s.id}_cancel` : s.id,
        cancelled ? "subscription_cancelled" : "subscription_created",
        monthly,
        s.status,
        s.customer,
        `Subscription ${s.status}`,
        s.canceled_at ?? s.created,
      ],
    );
    subs++;
  }

  await attributeRevenue();
  return { charges, subscriptions: subs };
}

/** Link revenue events to clients by stripe_customer_id, then by email. */
async function attributeRevenue(): Promise<void> {
  await sql(
    `UPDATE revenue_events r SET client_id = c.id
       FROM clients c
      WHERE r.client_id IS NULL
        AND c.stripe_customer_id IS NOT NULL
        AND r.stripe_customer_id = c.stripe_customer_id`,
  );
  await sql(
    `UPDATE revenue_events r SET client_id = c.id
       FROM clients c
      WHERE r.client_id IS NULL
        AND c.contact_email IS NOT NULL
        AND lower(r.customer_email) = lower(c.contact_email)`,
  );
}

export async function revenueSnapshot(): Promise<{
  last30Usd: number;
  prior30Usd: number;
  failedUsd: number;
  failedCount: number;
  contractedMrrUsd: number;
}> {
  const [row] = await sql<{
    last30: string; prior30: string; failed: string; failed_n: number;
  }>(
    `SELECT
       COALESCE(SUM(amount_cents) FILTER (
         WHERE type IN ('payment','invoice_paid') AND status <> 'failed'
           AND occurred_at > now() - interval '30 days'),0)::text AS last30,
       COALESCE(SUM(amount_cents) FILTER (
         WHERE type IN ('payment','invoice_paid') AND status <> 'failed'
           AND occurred_at > now() - interval '60 days'
           AND occurred_at <= now() - interval '30 days'),0)::text AS prior30,
       COALESCE(SUM(amount_cents) FILTER (
         WHERE status = 'failed' AND occurred_at > now() - interval '30 days'),0)::text AS failed,
       count(*) FILTER (
         WHERE status = 'failed' AND occurred_at > now() - interval '30 days')::int AS failed_n
     FROM revenue_events`,
  );

  const mrr = await one<{ mrr: string }>(
    `SELECT COALESCE(SUM(monthly_value),0)::text AS mrr FROM clients WHERE status='active'`,
  );

  return {
    last30Usd: Number(row.last30) / 100,
    prior30Usd: Number(row.prior30) / 100,
    failedUsd: Number(row.failed) / 100,
    failedCount: row.failed_n,
    contractedMrrUsd: Number(mrr?.mrr ?? 0),
  };
}
