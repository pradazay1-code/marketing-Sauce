-- ============================================================================
-- VERA — One Vision Marketing Business Agent
-- Postgres schema. Works on Vercel Postgres, Neon, or Supabase.
--
-- Apply with:  psql "$DATABASE_URL" -f db/schema.sql
-- Safe to re-run (idempotent).
-- ============================================================================

CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS "pg_trgm";

-- ============================================================================
-- CLIENTS — the businesses One Vision serves
-- ============================================================================
CREATE TABLE IF NOT EXISTS clients (
  id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
  slug            TEXT UNIQUE NOT NULL,
  name            TEXT NOT NULL,
  contact_name    TEXT,
  contact_email   TEXT,
  contact_phone   TEXT,
  industry        TEXT,
  city            TEXT,
  state           TEXT,
  website         TEXT,
  status          TEXT NOT NULL DEFAULT 'active'
                  CHECK (status IN ('prospect','onboarding','active','paused','churned')),
  monthly_value   NUMERIC(10,2) DEFAULT 0,
  started_at      DATE,
  stripe_customer_id TEXT,
  -- Agent-maintained health signal
  health_score    INT DEFAULT 70 CHECK (health_score BETWEEN 0 AND 100),
  health_notes    TEXT,
  last_reviewed_at TIMESTAMPTZ,
  last_contact_at TIMESTAMPTZ,
  notes           TEXT,
  created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_clients_status ON clients(status);
CREATE INDEX IF NOT EXISTS idx_clients_health ON clients(health_score);
CREATE INDEX IF NOT EXISTS idx_clients_name_trgm ON clients USING gin (name gin_trgm_ops);

-- ============================================================================
-- DELIVERABLES — work produced for each client
-- ============================================================================
CREATE TABLE IF NOT EXISTS deliverables (
  id            UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
  client_id     UUID NOT NULL REFERENCES clients(id) ON DELETE CASCADE,
  title         TEXT NOT NULL,
  kind          TEXT NOT NULL,   -- website | content | ad_campaign | seo | crm | report | other
  status        TEXT NOT NULL DEFAULT 'planned'
                CHECK (status IN ('planned','in_progress','delivered','blocked','cancelled')),
  detail        TEXT,
  url           TEXT,
  due_at        DATE,
  delivered_at  TIMESTAMPTZ,
  created_at    TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at    TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_deliverables_client ON deliverables(client_id);
CREATE INDEX IF NOT EXISTS idx_deliverables_status ON deliverables(status);
CREATE INDEX IF NOT EXISTS idx_deliverables_due ON deliverables(due_at);

-- ============================================================================
-- MEMORY — the agent's long-term knowledge base.
-- Every durable fact about the business lives here. Full-text searchable.
-- ============================================================================
CREATE TABLE IF NOT EXISTS memory (
  id            UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
  kind          TEXT NOT NULL DEFAULT 'fact'
                CHECK (kind IN ('fact','preference','decision','lesson','process','person','metric','risk')),
  subject       TEXT,                       -- who/what this is about ("Akira Real Estate", "pricing", "Isaiah")
  content       TEXT NOT NULL,
  source        TEXT,                       -- 'chat' | 'email' | 'stripe' | 'cron:daily' | 'manual'
  client_id     UUID REFERENCES clients(id) ON DELETE SET NULL,
  importance    INT NOT NULL DEFAULT 3 CHECK (importance BETWEEN 1 AND 5),
  confidence    NUMERIC(3,2) NOT NULL DEFAULT 0.80,
  tags          TEXT[] DEFAULT '{}',
  -- Reinforcement: facts that keep getting used stay hot
  hit_count     INT NOT NULL DEFAULT 0,
  last_used_at  TIMESTAMPTZ,
  superseded_by UUID REFERENCES memory(id) ON DELETE SET NULL,
  active        BOOLEAN NOT NULL DEFAULT true,
  search_vec    TSVECTOR,
  created_at    TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at    TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_memory_search ON memory USING gin(search_vec);
CREATE INDEX IF NOT EXISTS idx_memory_kind ON memory(kind);
CREATE INDEX IF NOT EXISTS idx_memory_subject ON memory(subject);
CREATE INDEX IF NOT EXISTS idx_memory_client ON memory(client_id);
CREATE INDEX IF NOT EXISTS idx_memory_active ON memory(active, importance DESC);
CREATE INDEX IF NOT EXISTS idx_memory_tags ON memory USING gin(tags);

CREATE OR REPLACE FUNCTION memory_search_trigger() RETURNS trigger AS $$
BEGIN
  NEW.search_vec :=
    setweight(to_tsvector('english', coalesce(NEW.subject,'')), 'A') ||
    setweight(to_tsvector('english', coalesce(NEW.content,'')), 'B') ||
    setweight(to_tsvector('english', coalesce(array_to_string(NEW.tags,' '),'')), 'C');
  NEW.updated_at := now();
  RETURN NEW;
END
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trg_memory_search ON memory;
CREATE TRIGGER trg_memory_search BEFORE INSERT OR UPDATE ON memory
  FOR EACH ROW EXECUTE FUNCTION memory_search_trigger();

-- ============================================================================
-- EMAILS — synced Gmail metadata + agent triage
-- ============================================================================
CREATE TABLE IF NOT EXISTS emails (
  id            UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
  gmail_id      TEXT UNIQUE NOT NULL,
  thread_id     TEXT,
  from_email    TEXT,
  from_name     TEXT,
  to_email      TEXT,
  subject       TEXT,
  snippet       TEXT,
  body_preview  TEXT,
  received_at   TIMESTAMPTZ,
  is_unread     BOOLEAN DEFAULT true,
  -- Agent triage
  category      TEXT,   -- client | lead | vendor | billing | personal | noise
  priority      TEXT CHECK (priority IN ('urgent','high','normal','low','ignore')),
  needs_reply   BOOLEAN DEFAULT false,
  summary       TEXT,
  suggested_action TEXT,
  client_id     UUID REFERENCES clients(id) ON DELETE SET NULL,
  processed_at  TIMESTAMPTZ,
  created_at    TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_emails_received ON emails(received_at DESC);
CREATE INDEX IF NOT EXISTS idx_emails_priority ON emails(priority);
CREATE INDEX IF NOT EXISTS idx_emails_needs_reply ON emails(needs_reply) WHERE needs_reply = true;
CREATE INDEX IF NOT EXISTS idx_emails_client ON emails(client_id);

-- ============================================================================
-- REVENUE — Stripe mirror
-- ============================================================================
CREATE TABLE IF NOT EXISTS revenue_events (
  id                UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
  stripe_id         TEXT UNIQUE NOT NULL,
  type              TEXT NOT NULL,  -- payment | refund | subscription_created | subscription_cancelled | invoice_paid | failed
  amount_cents      BIGINT NOT NULL DEFAULT 0,
  currency          TEXT NOT NULL DEFAULT 'usd',
  status            TEXT,
  customer_email    TEXT,
  customer_name     TEXT,
  stripe_customer_id TEXT,
  client_id         UUID REFERENCES clients(id) ON DELETE SET NULL,
  description       TEXT,
  occurred_at       TIMESTAMPTZ NOT NULL,
  raw               JSONB,
  created_at        TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_revenue_occurred ON revenue_events(occurred_at DESC);
CREATE INDEX IF NOT EXISTS idx_revenue_type ON revenue_events(type);
CREATE INDEX IF NOT EXISTS idx_revenue_client ON revenue_events(client_id);

-- ============================================================================
-- CONVERSATIONS — chat history with the agent
-- ============================================================================
CREATE TABLE IF NOT EXISTS conversations (
  id          UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
  title       TEXT,
  channel     TEXT NOT NULL DEFAULT 'web' CHECK (channel IN ('web','telegram','cron')),
  created_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at  TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS messages (
  id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
  conversation_id UUID NOT NULL REFERENCES conversations(id) ON DELETE CASCADE,
  role            TEXT NOT NULL CHECK (role IN ('user','assistant','tool')),
  content         TEXT NOT NULL,
  tool_calls      JSONB,
  tokens_in       INT,
  tokens_out      INT,
  cache_read      INT,
  created_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_messages_conv ON messages(conversation_id, created_at);

-- ============================================================================
-- ALERTS — everything the agent has flagged or sent
-- ============================================================================
CREATE TABLE IF NOT EXISTS alerts (
  id          UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
  severity    TEXT NOT NULL DEFAULT 'info' CHECK (severity IN ('info','warn','urgent')),
  title       TEXT NOT NULL,
  body        TEXT,
  category    TEXT,       -- revenue | client | inbox | task | system
  client_id   UUID REFERENCES clients(id) ON DELETE SET NULL,
  sent_telegram BOOLEAN DEFAULT false,
  acknowledged  BOOLEAN DEFAULT false,
  created_at  TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_alerts_created ON alerts(created_at DESC);
CREATE INDEX IF NOT EXISTS idx_alerts_unack ON alerts(acknowledged) WHERE acknowledged = false;

-- ============================================================================
-- TASKS — what Isaiah needs to do; the agent keeps him honest
-- ============================================================================
CREATE TABLE IF NOT EXISTS tasks (
  id          UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
  title       TEXT NOT NULL,
  detail      TEXT,
  status      TEXT NOT NULL DEFAULT 'open' CHECK (status IN ('open','doing','done','dropped')),
  priority    TEXT NOT NULL DEFAULT 'normal' CHECK (priority IN ('urgent','high','normal','low')),
  client_id   UUID REFERENCES clients(id) ON DELETE SET NULL,
  due_at      DATE,
  source      TEXT,   -- 'agent' | 'isaiah' | 'email'
  completed_at TIMESTAMPTZ,
  created_at  TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_tasks_status ON tasks(status, priority);
CREATE INDEX IF NOT EXISTS idx_tasks_due ON tasks(due_at) WHERE status IN ('open','doing');

-- ============================================================================
-- JOB RUNS — cron observability
-- ============================================================================
CREATE TABLE IF NOT EXISTS job_runs (
  id          UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
  job         TEXT NOT NULL,
  status      TEXT NOT NULL CHECK (status IN ('running','ok','error')),
  detail      TEXT,
  items       INT DEFAULT 0,
  started_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
  finished_at TIMESTAMPTZ
);

CREATE INDEX IF NOT EXISTS idx_jobruns_job ON job_runs(job, started_at DESC);

-- ============================================================================
-- INTEGRATION TOKENS — OAuth refresh tokens (Gmail etc.)
-- ============================================================================
CREATE TABLE IF NOT EXISTS integration_tokens (
  provider      TEXT PRIMARY KEY,
  access_token  TEXT,
  refresh_token TEXT,
  expires_at    TIMESTAMPTZ,
  scope         TEXT,
  account_email TEXT,
  updated_at    TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- ============================================================================
-- SEED — Isaiah's known business context so VERA starts informed
-- ============================================================================
INSERT INTO clients (slug, name, contact_name, industry, city, state, website, status, notes)
VALUES
  ('akira-real-estate','Akira Real Estate Agency','Kunal Patel','Real Estate','Dedham','MA',
   'https://akirarealestateagency.com','active',
   'Website, AI Instagram content, 5-campaign paid social program, local SEO + schema package.'),
  ('north-atlantic-tattoo','North Atlantic Tattoo',NULL,'Tattoo Studio','New Bedford','MA',
   NULL,'active','Website designed, built, and hosted. Delivered March 2026.'),
  ('ej-hardscaping','E&J Hardscaping & Landscaping Inc.',NULL,'Hardscaping Contractor',NULL,'MA',
   NULL,'active','Web presence and ongoing marketing support. Serves MA and RI.')
ON CONFLICT (slug) DO NOTHING;

INSERT INTO memory (kind, subject, content, source, importance, tags) VALUES
  ('fact','One Vision Marketing','One Vision Marketing Agency is a full-service marketing partnership founded by Isaiah Wright, based in Bridgewater, Massachusetts. Serves MA, RI, CT and nationwide.','seed',5,ARRAY['company','identity']),
  ('fact','Isaiah Wright','Isaiah Wright is the founder. B.A. Marketing from Bridgewater State University. Previously did marketing research for RECNA (Regional Economic Center for New Americans) in Bridgewater.','seed',5,ARRAY['founder','identity']),
  ('fact','Pricing','The flagship offer is the One Vision Growth Package at $300-$500/mo on a sliding scale based on ad spend and campaign scope. Stacked value is positioned at $5,800+/mo. No contracts, 30-day money-back guarantee, 48-hour onboarding.','seed',5,ARRAY['pricing','offer']),
  ('process','Sales','Sales methodology is built on Alex Hormozi frameworks: the Value Equation, Grand Slam Offer construction, and the CLOSER framework (Clarify, Label, Overview, Sell the value, Explain, Reinforce).','seed',4,ARRAY['sales','process']),
  ('preference','Isaiah','Prefers direct, no-fluff communication. Wants honest pushback rather than agreement. Values shipping fast and iterating over waiting for perfect.','seed',5,ARRAY['communication','preference']),
  ('preference','Deliverables','All client-facing HTML files must be fully self-contained — no external CDN fonts, images, or scripts. External dependencies fail on mobile and restricted networks.','seed',4,ARRAY['standards','delivery']),
  ('fact','Brand','Brand colors are navy #1e3a5f primary with lighter navy accents. Tagline: "One Vision. One Team. Real Growth." Instagram @onevisionmarketing1. Site: Onevisionmarketingagency.com.','seed',4,ARRAY['brand']),
  ('process','Client Care','As of September 2026 One Vision runs a monthly community update program — a recurring briefing to every client, plus a monthly giveaway where the top-performing client receives one month of service free.','seed',4,ARRAY['retention','process'])
ON CONFLICT DO NOTHING;
