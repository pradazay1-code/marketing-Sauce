import sqlite3
import os
import json
from datetime import datetime, date

from pg_adapter import is_postgres, get_pg_connection, PGConnection

DB_PATH = os.environ.get("LEADGEN_DB_PATH") or os.path.join(os.path.dirname(os.path.abspath(__file__)), "leads.db")

ALLOWED_COLUMNS = {
    "business_name", "owner_name", "category", "business_type", "phone", "email",
    "address", "city", "state", "zip_code", "has_website", "website_url",
    "website_score", "has_social_media", "social_links", "marketing_score",
    "lead_score", "filing_date", "date_found", "source", "status", "notes",
    "priority", "contacted", "contact_date", "tags", "next_followup",
    "created_at", "updated_at",
    "tech_stack_json", "review_count", "review_rating", "employee_count",
    "icp_score", "email_verified", "segment",
}

PIPELINE_STAGES = ["new", "contacted", "responded", "qualified", "proposal", "won", "lost"]


_pg_consecutive_errors = 0
_pg_max_retries = 3


def get_db():
    """Return a database connection.

    If DATABASE_URL is set, ALWAYS use PostgreSQL. We never silently fall
    back to SQLite when Postgres is configured, because on ephemeral hosts
    (Render free) that would silently lose all writes. Instead we retry a
    few times, then raise.
    """
    global _pg_consecutive_errors
    if is_postgres():
        last_err = None
        for attempt in range(_pg_max_retries):
            try:
                conn = get_pg_connection()
                _pg_consecutive_errors = 0
                return conn
            except Exception as e:
                last_err = e
                _pg_consecutive_errors += 1
                print(f"[DB] PostgreSQL connection failed (attempt {attempt + 1}/{_pg_max_retries}): {str(e)[:200]}")
        raise RuntimeError(
            f"PostgreSQL unavailable after {_pg_max_retries} attempts. "
            f"Refusing to use ephemeral SQLite to prevent data loss. "
            f"Check DATABASE_URL and Supabase status. Last error: {str(last_err)[:200]}"
        )

    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


def init_db():
    try:
        _init_db_inner()
    except Exception as e:
        print(f"[DB] Warning during init: {e}")


def _init_db_inner():
    conn = get_db()
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS leads (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            business_name TEXT NOT NULL,
            owner_name TEXT DEFAULT '',
            category TEXT DEFAULT '',
            business_type TEXT DEFAULT '',
            phone TEXT DEFAULT '',
            email TEXT DEFAULT '',
            address TEXT DEFAULT '',
            city TEXT DEFAULT '',
            state TEXT DEFAULT '',
            zip_code TEXT DEFAULT '',
            has_website INTEGER DEFAULT 0,
            website_url TEXT DEFAULT '',
            website_score INTEGER DEFAULT 0,
            has_social_media INTEGER DEFAULT 0,
            social_links TEXT DEFAULT '',
            marketing_score INTEGER DEFAULT 0,
            lead_score INTEGER DEFAULT 50,
            filing_date TEXT DEFAULT '',
            date_found TEXT DEFAULT '',
            source TEXT DEFAULT '',
            status TEXT DEFAULT 'new',
            notes TEXT DEFAULT '',
            priority TEXT DEFAULT 'medium',
            contacted INTEGER DEFAULT 0,
            contact_date TEXT DEFAULT '',
            next_followup TEXT DEFAULT '',
            tags TEXT DEFAULT '',
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            updated_at TEXT DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS activities (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            lead_id INTEGER NOT NULL,
            activity_type TEXT NOT NULL,
            note TEXT DEFAULT '',
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (lead_id) REFERENCES leads(id) ON DELETE CASCADE
        );

        CREATE TABLE IF NOT EXISTS scrape_log (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            source TEXT NOT NULL,
            state TEXT NOT NULL,
            leads_found INTEGER DEFAULT 0,
            leads_added INTEGER DEFAULT 0,
            started_at TEXT DEFAULT CURRENT_TIMESTAMP,
            finished_at TEXT,
            status TEXT DEFAULT 'running',
            error TEXT DEFAULT ''
        );

        CREATE TABLE IF NOT EXISTS scrape_status (
            id INTEGER PRIMARY KEY CHECK (id = 1),
            running INTEGER DEFAULT 0,
            source TEXT DEFAULT '',
            state TEXT DEFAULT '',
            current_step TEXT DEFAULT '',
            progress_pct INTEGER DEFAULT 0,
            leads_so_far INTEGER DEFAULT 0,
            started_at TEXT DEFAULT '',
            updated_at TEXT DEFAULT '',
            last_message TEXT DEFAULT ''
        );

        INSERT OR IGNORE INTO scrape_status (id, running) VALUES (1, 0);

        CREATE TABLE IF NOT EXISTS saved_searches (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            filters TEXT NOT NULL,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS email_templates (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            subject TEXT NOT NULL DEFAULT '',
            body TEXT NOT NULL DEFAULT '',
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            updated_at TEXT DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS email_log (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            lead_id INTEGER,
            to_email TEXT NOT NULL,
            subject TEXT NOT NULL DEFAULT '',
            body TEXT NOT NULL DEFAULT '',
            template_id INTEGER,
            status TEXT DEFAULT 'sent',
            sent_at TEXT DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (lead_id) REFERENCES leads(id) ON DELETE SET NULL
        );

        CREATE TABLE IF NOT EXISTS email_settings (
            id INTEGER PRIMARY KEY CHECK (id = 1),
            smtp_host TEXT DEFAULT '',
            smtp_port INTEGER DEFAULT 587,
            smtp_user TEXT DEFAULT '',
            smtp_pass TEXT DEFAULT '',
            from_name TEXT DEFAULT 'AventisAI',
            from_email TEXT DEFAULT '',
            enabled INTEGER DEFAULT 0
        );

        INSERT OR IGNORE INTO email_settings (id) VALUES (1);

        CREATE INDEX IF NOT EXISTS idx_leads_state ON leads(state);
        CREATE INDEX IF NOT EXISTS idx_leads_city ON leads(city);
        CREATE INDEX IF NOT EXISTS idx_leads_category ON leads(category);
        CREATE INDEX IF NOT EXISTS idx_leads_status ON leads(status);
        CREATE INDEX IF NOT EXISTS idx_leads_has_website ON leads(has_website);
        CREATE INDEX IF NOT EXISTS idx_leads_date_found ON leads(date_found);
        CREATE INDEX IF NOT EXISTS idx_leads_lead_score ON leads(lead_score);
        CREATE INDEX IF NOT EXISTS idx_leads_priority ON leads(priority);
        CREATE INDEX IF NOT EXISTS idx_leads_phone ON leads(phone);
        CREATE INDEX IF NOT EXISTS idx_leads_email ON leads(email);
        CREATE INDEX IF NOT EXISTS idx_activities_lead ON activities(lead_id);
        CREATE INDEX IF NOT EXISTS idx_activities_created ON activities(created_at);
        CREATE INDEX IF NOT EXISTS idx_email_log_lead ON email_log(lead_id);
    """)

    if isinstance(conn, PGConnection):
        cur = conn.execute(
            "SELECT column_name FROM information_schema.columns WHERE table_name = 'leads'",
        )
        existing_cols = {row["column_name"] for row in cur.fetchall()}
    else:
        cur = conn.execute("PRAGMA table_info(leads)")
        existing_cols = {row[1] for row in cur.fetchall()}
    for col, ddl in [
        ("lead_score", "ALTER TABLE leads ADD COLUMN lead_score INTEGER DEFAULT 50"),
        ("tags", "ALTER TABLE leads ADD COLUMN tags TEXT DEFAULT ''"),
        ("next_followup", "ALTER TABLE leads ADD COLUMN next_followup TEXT DEFAULT ''"),
        ("tech_stack_json", "ALTER TABLE leads ADD COLUMN tech_stack_json TEXT DEFAULT ''"),
        ("review_count", "ALTER TABLE leads ADD COLUMN review_count INTEGER DEFAULT 0"),
        ("review_rating", "ALTER TABLE leads ADD COLUMN review_rating REAL DEFAULT 0"),
        ("employee_count", "ALTER TABLE leads ADD COLUMN employee_count INTEGER DEFAULT 0"),
        ("icp_score", "ALTER TABLE leads ADD COLUMN icp_score INTEGER DEFAULT 0"),
        ("email_verified", "ALTER TABLE leads ADD COLUMN email_verified INTEGER DEFAULT 0"),
        ("segment", "ALTER TABLE leads ADD COLUMN segment TEXT DEFAULT ''"),
    ]:
        if col not in existing_cols:
            try:
                conn.execute(ddl)
            except Exception:
                pass

    conn.executescript("""
        CREATE TABLE IF NOT EXISTS campaigns (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            campaign_key TEXT NOT NULL DEFAULT '',
            status TEXT DEFAULT 'draft',
            target_filters_json TEXT DEFAULT '{}',
            sequence_steps_json TEXT DEFAULT '[]',
            total_sent INTEGER DEFAULT 0,
            total_opened INTEGER DEFAULT 0,
            total_replied INTEGER DEFAULT 0,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            updated_at TEXT DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS sequence_runs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            lead_id INTEGER NOT NULL,
            campaign_id INTEGER,
            campaign_key TEXT DEFAULT '',
            current_step INTEGER DEFAULT 0,
            status TEXT DEFAULT 'active',
            next_send_at TEXT DEFAULT '',
            last_sent_at TEXT DEFAULT '',
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (lead_id) REFERENCES leads(id) ON DELETE CASCADE
        );

        CREATE TABLE IF NOT EXISTS automation_jobs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            job_type TEXT NOT NULL,
            config_json TEXT DEFAULT '{}',
            status TEXT DEFAULT 'pending',
            result_json TEXT DEFAULT '{}',
            started_at TEXT DEFAULT '',
            finished_at TEXT DEFAULT '',
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        );

        CREATE INDEX IF NOT EXISTS idx_sequence_runs_lead ON sequence_runs(lead_id);
        CREATE INDEX IF NOT EXISTS idx_sequence_runs_status ON sequence_runs(status);
        CREATE INDEX IF NOT EXISTS idx_sequence_runs_next ON sequence_runs(next_send_at);
        CREATE INDEX IF NOT EXISTS idx_automation_jobs_status ON automation_jobs(status);
        CREATE INDEX IF NOT EXISTS idx_leads_icp_score ON leads(icp_score);
        CREATE INDEX IF NOT EXISTS idx_leads_segment ON leads(segment);
    """)

    conn.commit()
    conn.close()


def _sanitize_keys(data):
    return {k: v for k, v in data.items() if k in ALLOWED_COLUMNS}


def _phone_digits(phone):
    """Extract last 10 digits for dedup comparison."""
    digits = "".join(c for c in (phone or "") if c.isdigit())
    if len(digits) == 11 and digits.startswith("1"):
        digits = digits[1:]
    return digits[-10:] if len(digits) >= 10 else ""


def _build_phone_index(conn):
    """Build an in-memory set of all existing 10-digit phone numbers for fast dedup."""
    index = set()
    for row in conn.execute("SELECT phone FROM leads WHERE phone != ''").fetchall():
        digits = _phone_digits(row[0] if not isinstance(row, dict) else row.get("phone", ""))
        if digits and len(digits) == 10:
            index.add(digits)
    return index


def add_lead(lead_data, dedupe_by_phone=True, phone_index=None):
    """Add a lead with deduplication by name+city+state AND phone.

    Pass a precomputed phone_index (set of 10-digit strings) to skip the
    per-call scan when doing bulk inserts.
    """
    conn = get_db()
    try:
        biz_name = (lead_data.get("business_name") or "").strip()
        if not biz_name:
            return None

        city = (lead_data.get("city") or "").strip()
        state = (lead_data.get("state") or "").strip()
        phone_digits = _phone_digits(lead_data.get("phone", ""))

        existing = conn.execute(
            "SELECT id FROM leads WHERE LOWER(business_name) = LOWER(?) AND LOWER(city) = LOWER(?) AND state = ?",
            (biz_name, city, state)
        ).fetchone()
        if existing:
            return None

        if dedupe_by_phone and phone_digits and len(phone_digits) == 10:
            if phone_index is not None:
                if phone_digits in phone_index:
                    return None
            else:
                hit = conn.execute(
                    "SELECT 1 FROM leads WHERE phone != '' LIMIT 1"
                ).fetchone()
                if hit:
                    all_phones = conn.execute(
                        "SELECT phone FROM leads WHERE phone != ''"
                    ).fetchall()
                    for row in all_phones:
                        phone_val = row[0] if not isinstance(row, dict) else row.get("phone", "")
                        if _phone_digits(phone_val) == phone_digits:
                            return None

        safe_data = _sanitize_keys(lead_data)
        safe_data.setdefault("date_found", date.today().isoformat())
        safe_data["created_at"] = datetime.now().isoformat()
        safe_data["updated_at"] = datetime.now().isoformat()

        columns = ", ".join(safe_data.keys())
        placeholders = ", ".join(["?"] * len(safe_data))
        values = list(safe_data.values())

        cursor = conn.execute(f"INSERT INTO leads ({columns}) VALUES ({placeholders})", values)
        lead_id = cursor.lastrowid

        conn.execute(
            "INSERT INTO activities (lead_id, activity_type, note) VALUES (?, ?, ?)",
            (lead_id, "created", f"Lead added from {safe_data.get('source', 'manual')}")
        )

        conn.commit()
        if phone_index is not None and phone_digits and len(phone_digits) == 10:
            phone_index.add(phone_digits)
        return lead_id
    except Exception:
        try:
            conn.rollback()
        except Exception:
            pass
        raise
    finally:
        try:
            conn.close()
        except Exception:
            pass


def add_leads_bulk(leads_list):
    """Bulk insert with O(n) dedup — loads existing phone index once."""
    if not leads_list:
        return 0
    conn = get_db()
    try:
        phone_index = _build_phone_index(conn)
    finally:
        conn.close()

    added = 0
    for lead in leads_list:
        try:
            result = add_lead(dict(lead), phone_index=phone_index)
            if result:
                added += 1
        except Exception as e:
            print(f"[add_leads_bulk] skipping lead due to error: {str(e)[:100]}")
            continue
    return added


def get_leads(filters=None, limit=200, offset=0, sort_by="date_found", sort_dir="DESC"):
    conn = get_db()
    query = "SELECT * FROM leads WHERE 1=1"
    params = []

    if filters:
        if filters.get("state"):
            query += " AND state = ?"
            params.append(filters["state"])
        if filters.get("city"):
            query += " AND city LIKE ?"
            params.append(f"%{filters['city']}%")
        if filters.get("category"):
            query += " AND category LIKE ?"
            params.append(f"%{filters['category']}%")
        if filters.get("has_website") is not None:
            query += " AND has_website = ?"
            params.append(int(filters["has_website"]))
        if filters.get("status"):
            query += " AND status = ?"
            params.append(filters["status"])
        if filters.get("priority"):
            query += " AND priority = ?"
            params.append(filters["priority"])
        if filters.get("tag"):
            query += " AND tags LIKE ?"
            params.append(f"%{filters['tag']}%")
        if filters.get("source"):
            query += " AND source LIKE ?"
            params.append(f"%{filters['source']}%")
        if filters.get("search"):
            query += " AND (business_name LIKE ? OR owner_name LIKE ? OR notes LIKE ? OR phone LIKE ? OR email LIKE ?)"
            s = f"%{filters['search']}%"
            params.extend([s, s, s, s, s])
        if filters.get("min_score") is not None:
            query += " AND lead_score >= ?"
            params.append(int(filters["min_score"]))
        if filters.get("date_from"):
            query += " AND date_found >= ?"
            params.append(filters["date_from"])
        if filters.get("date_to"):
            query += " AND date_found <= ?"
            params.append(filters["date_to"])
        if filters.get("has_phone"):
            query += " AND phone != ''"
        if filters.get("has_email"):
            query += " AND email != ''"
        if filters.get("ids"):
            id_list = [int(i) for i in filters["ids"] if isinstance(i, int) or (isinstance(i, str) and i.isdigit())]
            if id_list:
                placeholders = ", ".join(["?"] * len(id_list))
                query += f" AND id IN ({placeholders})"
                params.extend(id_list)

    allowed_sorts = {"date_found", "business_name", "city", "state", "lead_score",
                     "marketing_score", "priority", "created_at", "category", "email"}
    if sort_by not in allowed_sorts:
        sort_by = "date_found"
    sort_dir = "ASC" if sort_dir.upper() == "ASC" else "DESC"
    query += f" ORDER BY {sort_by} {sort_dir} LIMIT ? OFFSET ?"
    params.extend([limit, offset])

    rows = conn.execute(query, params).fetchall()
    conn.close()
    return [dict(row) for row in rows]


def count_leads(filters=None):
    conn = get_db()
    query = "SELECT COUNT(*) FROM leads WHERE 1=1"
    params = []

    if filters:
        if filters.get("state"):
            query += " AND state = ?"
            params.append(filters["state"])
        if filters.get("status"):
            query += " AND status = ?"
            params.append(filters["status"])
        if filters.get("has_website") is not None:
            query += " AND has_website = ?"
            params.append(int(filters["has_website"]))
        if filters.get("priority"):
            query += " AND priority = ?"
            params.append(filters["priority"])
        if filters.get("search"):
            query += " AND (business_name LIKE ? OR owner_name LIKE ? OR notes LIKE ? OR phone LIKE ? OR email LIKE ?)"
            s = f"%{filters['search']}%"
            params.extend([s, s, s, s, s])
        if filters.get("category"):
            query += " AND category LIKE ?"
            params.append(f"%{filters['category']}%")
        if filters.get("min_score") is not None:
            query += " AND lead_score >= ?"
            params.append(int(filters["min_score"]))
        if filters.get("has_phone"):
            query += " AND phone != ''"
        if filters.get("has_email"):
            query += " AND email != ''"

    count = conn.execute(query, params).fetchone()[0]
    conn.close()
    return count


def get_lead_by_id(lead_id):
    conn = get_db()
    row = conn.execute("SELECT * FROM leads WHERE id = ?", (lead_id,)).fetchone()
    conn.close()
    return dict(row) if row else None


def update_lead(lead_id, updates, log_activity=True):
    safe_updates = _sanitize_keys(updates)
    if not safe_updates:
        return
    conn = get_db()
    try:
        existing = conn.execute("SELECT id FROM leads WHERE id = ?", (lead_id,)).fetchone()
        if not existing:
            return

        safe_updates["updated_at"] = datetime.now().isoformat()
        set_clause = ", ".join([f"{k} = ?" for k in safe_updates.keys()])
        values = list(safe_updates.values()) + [lead_id]
        conn.execute(f"UPDATE leads SET {set_clause} WHERE id = ?", values)

        if log_activity and "status" in updates:
            conn.execute(
                "INSERT INTO activities (lead_id, activity_type, note) VALUES (?, ?, ?)",
                (lead_id, "status_change", f"Status changed to {updates['status']}")
            )

        conn.commit()
    finally:
        conn.close()


def delete_lead(lead_id):
    conn = get_db()
    try:
        conn.execute("DELETE FROM activities WHERE lead_id = ?", (lead_id,))
        conn.execute("DELETE FROM leads WHERE id = ?", (lead_id,))
        conn.commit()
    finally:
        conn.close()


def add_activity(lead_id, activity_type, note=""):
    conn = get_db()
    conn.execute(
        "INSERT INTO activities (lead_id, activity_type, note) VALUES (?, ?, ?)",
        (lead_id, activity_type, note)
    )
    conn.commit()
    conn.close()


def get_activities(lead_id, limit=50):
    conn = get_db()
    rows = conn.execute(
        "SELECT * FROM activities WHERE lead_id = ? ORDER BY created_at DESC LIMIT ?",
        (lead_id, limit)
    ).fetchall()
    conn.close()
    return [dict(row) for row in rows]


def get_recent_activities(limit=20):
    conn = get_db()
    rows = conn.execute("""
        SELECT a.*, l.business_name, l.city, l.state
        FROM activities a
        JOIN leads l ON a.lead_id = l.id
        ORDER BY a.created_at DESC
        LIMIT ?
    """, (limit,)).fetchall()
    conn.close()
    return [dict(row) for row in rows]


def get_stats():
    conn = get_db()
    stats = {}
    stats["total"] = conn.execute("SELECT COUNT(*) FROM leads").fetchone()[0]
    stats["no_website"] = conn.execute("SELECT COUNT(*) FROM leads WHERE has_website = 0").fetchone()[0]
    stats["with_phone"] = conn.execute("SELECT COUNT(*) FROM leads WHERE phone != ''").fetchone()[0]
    stats["with_email"] = conn.execute("SELECT COUNT(*) FROM leads WHERE email != ''").fetchone()[0]
    stats["new_today"] = conn.execute(
        "SELECT COUNT(*) FROM leads WHERE date_found = ?", (date.today().isoformat(),)
    ).fetchone()[0]
    if isinstance(conn, PGConnection):
        stats["new_this_week"] = conn.execute(
            "SELECT COUNT(*) FROM leads WHERE date_found != '' AND date_found::date >= CURRENT_DATE - INTERVAL '7 days'"
        ).fetchone()[0]
    else:
        stats["new_this_week"] = conn.execute(
            "SELECT COUNT(*) FROM leads WHERE date_found >= date('now', '-7 days')"
        ).fetchone()[0]
    stats["contacted"] = conn.execute("SELECT COUNT(*) FROM leads WHERE contacted = 1 OR status != 'new'").fetchone()[0]
    stats["high_priority"] = conn.execute("SELECT COUNT(*) FROM leads WHERE priority = 'high'").fetchone()[0]
    stats["needs_followup"] = conn.execute(
        "SELECT COUNT(*) FROM leads WHERE next_followup != '' AND next_followup <= ?",
        (date.today().isoformat(),)
    ).fetchone()[0]
    stats["emails_sent"] = conn.execute("SELECT COUNT(*) FROM email_log").fetchone()[0] if table_exists(conn, "email_log") else 0

    stats["by_state"] = {}
    for row in conn.execute("SELECT state, COUNT(*) as cnt FROM leads WHERE state != '' GROUP BY state ORDER BY cnt DESC"):
        stats["by_state"][row[0]] = row[1]

    stats["by_category"] = {}
    for row in conn.execute("SELECT category, COUNT(*) as cnt FROM leads WHERE category != '' GROUP BY category ORDER BY cnt DESC LIMIT 10"):
        stats["by_category"][row[0]] = row[1]

    stats["by_priority"] = {}
    for row in conn.execute("SELECT priority, COUNT(*) as cnt FROM leads GROUP BY priority"):
        stats["by_priority"][row[0]] = row[1]

    stats["by_status"] = {}
    for row in conn.execute("SELECT status, COUNT(*) as cnt FROM leads GROUP BY status"):
        stats["by_status"][row[0]] = row[1]

    stats["by_source"] = {}
    for row in conn.execute("SELECT source, COUNT(*) as cnt FROM leads WHERE source != '' GROUP BY source ORDER BY cnt DESC LIMIT 10"):
        stats["by_source"][row[0]] = row[1]

    total = stats["total"]
    if total > 0:
        stats["conversion_rate"] = round((stats["by_status"].get("won", 0) / total) * 100, 1)
        stats["contact_rate"] = round((stats["contacted"] / total) * 100, 1)
    else:
        stats["conversion_rate"] = 0.0
        stats["contact_rate"] = 0.0

    conn.close()
    return stats


def table_exists(conn, table_name):
    if isinstance(conn, PGConnection):
        row = conn.execute(
            "SELECT table_name FROM information_schema.tables WHERE table_name=?",
            (table_name,)
        ).fetchone()
    else:
        row = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name=?",
            (table_name,)
        ).fetchone()
    return row is not None


def get_pipeline_data():
    conn = get_db()
    pipeline = {}
    for stage in PIPELINE_STAGES:
        rows = conn.execute(
            "SELECT id, business_name, city, state, phone, email, priority, lead_score, category FROM leads WHERE status = ? ORDER BY lead_score DESC, date_found DESC LIMIT 100",
            (stage,)
        ).fetchall()
        pipeline[stage] = [dict(row) for row in rows]
    conn.close()
    return pipeline


def get_scrape_logs(limit=20):
    conn = get_db()
    rows = conn.execute(
        "SELECT * FROM scrape_log ORDER BY started_at DESC LIMIT ?", (limit,)
    ).fetchall()
    conn.close()
    return [dict(row) for row in rows]


def clear_scrape_logs(only_errors=False):
    conn = get_db()
    if only_errors:
        conn.execute("DELETE FROM scrape_log WHERE status = 'error'")
    else:
        conn.execute("DELETE FROM scrape_log")
    conn.commit()
    conn.close()


def log_scrape(source, state, leads_found=0, leads_added=0, status="completed", error=""):
    conn = get_db()
    conn.execute(
        "INSERT INTO scrape_log (source, state, leads_found, leads_added, finished_at, status, error) VALUES (?, ?, ?, ?, ?, ?, ?)",
        (source, state, leads_found, leads_added, datetime.now().isoformat(), status, error)
    )
    conn.commit()
    conn.close()


def update_scrape_status(running=None, source=None, state=None, current_step=None,
                          progress_pct=None, leads_so_far=None, last_message=None,
                          starting=False):
    conn = get_db()
    fields = []
    values = []
    if running is not None:
        fields.append("running = ?")
        values.append(int(running))
    if source is not None:
        fields.append("source = ?")
        values.append(source)
    if state is not None:
        fields.append("state = ?")
        values.append(state)
    if current_step is not None:
        fields.append("current_step = ?")
        values.append(current_step)
    if progress_pct is not None:
        fields.append("progress_pct = ?")
        values.append(int(progress_pct))
    if leads_so_far is not None:
        fields.append("leads_so_far = ?")
        values.append(int(leads_so_far))
    if last_message is not None:
        fields.append("last_message = ?")
        values.append(last_message)
    if starting:
        fields.append("started_at = ?")
        values.append(datetime.now().isoformat())
    fields.append("updated_at = ?")
    values.append(datetime.now().isoformat())
    values.append(1)
    conn.execute(f"UPDATE scrape_status SET {', '.join(fields)} WHERE id = ?", values)
    conn.commit()
    conn.close()


def get_scrape_status():
    conn = get_db()
    row = conn.execute("SELECT * FROM scrape_status WHERE id = 1").fetchone()
    conn.close()
    return dict(row) if row else {"running": 0}


# --- Email system ---

def get_email_settings():
    conn = get_db()
    row = conn.execute("SELECT * FROM email_settings WHERE id = 1").fetchone()
    conn.close()
    return dict(row) if row else {}


def update_email_settings(settings):
    conn = get_db()
    allowed = {"smtp_host", "smtp_port", "smtp_user", "smtp_pass", "from_name", "from_email", "enabled"}
    safe = {k: v for k, v in settings.items() if k in allowed}
    if not safe:
        conn.close()
        return
    set_clause = ", ".join([f"{k} = ?" for k in safe.keys()])
    values = list(safe.values()) + [1]
    conn.execute(f"UPDATE email_settings SET {set_clause} WHERE id = ?", values)
    conn.commit()
    conn.close()


def save_email_template(name, subject, body, template_id=None):
    conn = get_db()
    if template_id:
        conn.execute(
            "UPDATE email_templates SET name=?, subject=?, body=?, updated_at=? WHERE id=?",
            (name, subject, body, datetime.now().isoformat(), template_id)
        )
    else:
        conn.execute(
            "INSERT INTO email_templates (name, subject, body) VALUES (?, ?, ?)",
            (name, subject, body)
        )
    conn.commit()
    conn.close()


def get_email_templates():
    conn = get_db()
    rows = conn.execute("SELECT * FROM email_templates ORDER BY created_at DESC").fetchall()
    conn.close()
    return [dict(row) for row in rows]


def get_email_template(template_id):
    conn = get_db()
    row = conn.execute("SELECT * FROM email_templates WHERE id = ?", (template_id,)).fetchone()
    conn.close()
    return dict(row) if row else None


def delete_email_template(template_id):
    conn = get_db()
    conn.execute("DELETE FROM email_templates WHERE id = ?", (template_id,))
    conn.commit()
    conn.close()


def log_email(lead_id, to_email, subject, body, template_id=None):
    conn = get_db()
    conn.execute(
        "INSERT INTO email_log (lead_id, to_email, subject, body, template_id) VALUES (?, ?, ?, ?, ?)",
        (lead_id, to_email, subject, body, template_id)
    )
    if lead_id:
        conn.execute(
            "INSERT INTO activities (lead_id, activity_type, note) VALUES (?, ?, ?)",
            (lead_id, "email_sent", f"Email sent: {subject}")
        )
    conn.commit()
    conn.close()


def get_email_log(limit=50, lead_id=None):
    conn = get_db()
    if lead_id:
        rows = conn.execute(
            "SELECT e.*, l.business_name FROM email_log e LEFT JOIN leads l ON e.lead_id = l.id WHERE e.lead_id = ? ORDER BY e.sent_at DESC LIMIT ?",
            (lead_id, limit)
        ).fetchall()
    else:
        rows = conn.execute(
            "SELECT e.*, l.business_name FROM email_log e LEFT JOIN leads l ON e.lead_id = l.id ORDER BY e.sent_at DESC LIMIT ?",
            (limit,)
        ).fetchall()
    conn.close()
    return [dict(row) for row in rows]


def save_search(name, filters):
    conn = get_db()
    conn.execute(
        "INSERT INTO saved_searches (name, filters) VALUES (?, ?)",
        (name, json.dumps(filters))
    )
    conn.commit()
    conn.close()


def get_saved_searches():
    conn = get_db()
    rows = conn.execute("SELECT * FROM saved_searches ORDER BY created_at DESC").fetchall()
    conn.close()
    result = []
    for row in rows:
        d = dict(row)
        try:
            d["filters"] = json.loads(d["filters"])
        except (json.JSONDecodeError, TypeError):
            d["filters"] = {}
        result.append(d)
    return result


def delete_saved_search(search_id):
    conn = get_db()
    conn.execute("DELETE FROM saved_searches WHERE id = ?", (search_id,))
    conn.commit()
    conn.close()


def get_recent_leads(limit=5):
    conn = get_db()
    rows = conn.execute(
        "SELECT id, business_name, category, city, state, priority, date_found, has_website, phone, email FROM leads ORDER BY created_at DESC LIMIT ?",
        (limit,)
    ).fetchall()
    conn.close()
    return [dict(row) for row in rows]


def export_csv(filters=None):
    leads = get_leads(filters=filters, limit=100000)
    if not leads:
        return ""
    headers = ["business_name", "owner_name", "category", "business_type", "phone", "email",
               "address", "city", "state", "zip_code", "has_website", "website_url",
               "marketing_score", "lead_score", "priority", "status", "tags",
               "date_found", "source", "notes"]
    lines = [",".join(headers)]
    for lead in leads:
        row = []
        for h in headers:
            val = str(lead.get(h, "")).replace("\n", " ").replace("\r", " ").replace('"', '""')
            if "," in val or '"' in val:
                val = f'"{val}"'
            row.append(val)
        lines.append(",".join(row))
    return "\n".join(lines)


# --- Campaigns & Sequences ---

def save_campaign(name, campaign_key, target_filters=None, sequence_steps=None, campaign_id=None):
    conn = get_db()
    if campaign_id:
        conn.execute(
            "UPDATE campaigns SET name=?, campaign_key=?, target_filters_json=?, sequence_steps_json=?, updated_at=? WHERE id=?",
            (name, campaign_key, json.dumps(target_filters or {}), json.dumps(sequence_steps or []),
             datetime.now().isoformat(), campaign_id)
        )
    else:
        conn.execute(
            "INSERT INTO campaigns (name, campaign_key, target_filters_json, sequence_steps_json) VALUES (?, ?, ?, ?)",
            (name, campaign_key, json.dumps(target_filters or {}), json.dumps(sequence_steps or []))
        )
    conn.commit()
    conn.close()


def get_campaigns():
    conn = get_db()
    rows = conn.execute("SELECT * FROM campaigns ORDER BY created_at DESC").fetchall()
    conn.close()
    result = []
    for row in rows:
        d = dict(row)
        try:
            d["target_filters"] = json.loads(d.get("target_filters_json") or "{}")
        except (json.JSONDecodeError, TypeError):
            d["target_filters"] = {}
        try:
            d["sequence_steps"] = json.loads(d.get("sequence_steps_json") or "[]")
        except (json.JSONDecodeError, TypeError):
            d["sequence_steps"] = []
        result.append(d)
    return result


def update_campaign_stats(campaign_id, sent=0, opened=0, replied=0):
    conn = get_db()
    conn.execute(
        "UPDATE campaigns SET total_sent = total_sent + ?, total_opened = total_opened + ?, total_replied = total_replied + ?, updated_at = ? WHERE id = ?",
        (sent, opened, replied, datetime.now().isoformat(), campaign_id)
    )
    conn.commit()
    conn.close()


def add_sequence_run(lead_id, campaign_key, campaign_id=None):
    conn = get_db()
    existing = conn.execute(
        "SELECT id FROM sequence_runs WHERE lead_id = ? AND campaign_key = ? AND status = 'active'",
        (lead_id, campaign_key)
    ).fetchone()
    if existing:
        conn.close()
        return None
    cursor = conn.execute(
        "INSERT INTO sequence_runs (lead_id, campaign_key, campaign_id, status) VALUES (?, ?, ?, 'active')",
        (lead_id, campaign_key, campaign_id)
    )
    run_id = cursor.lastrowid
    conn.commit()
    conn.close()
    return run_id


def get_sequence_runs(status=None, due_before=None):
    conn = get_db()
    query = """SELECT sr.*, l.business_name, l.email, l.city, l.state, l.phone, l.icp_score, l.lead_score
               FROM sequence_runs sr JOIN leads l ON sr.lead_id = l.id WHERE 1=1"""
    params = []
    if status:
        query += " AND sr.status = ?"
        params.append(status)
    if due_before:
        query += " AND sr.next_send_at != '' AND sr.next_send_at <= ?"
        params.append(due_before)
    query += " ORDER BY sr.created_at DESC"
    rows = conn.execute(query, params).fetchall()
    conn.close()
    return [dict(row) for row in rows]


def update_sequence_run(run_id, **kwargs):
    conn = get_db()
    fields = []
    values = []
    for k, v in kwargs.items():
        if k in ("current_step", "status", "next_send_at", "last_sent_at"):
            fields.append(f"{k} = ?")
            values.append(v)
    if not fields:
        conn.close()
        return
    values.append(run_id)
    conn.execute(f"UPDATE sequence_runs SET {', '.join(fields)} WHERE id = ?", values)
    conn.commit()
    conn.close()


# --- Automation Jobs ---

def add_automation_job(job_type, config=None):
    conn = get_db()
    cursor = conn.execute(
        "INSERT INTO automation_jobs (job_type, config_json, status, started_at) VALUES (?, ?, 'running', ?)",
        (job_type, json.dumps(config or {}), datetime.now().isoformat())
    )
    job_id = cursor.lastrowid
    conn.commit()
    conn.close()
    return job_id


def finish_automation_job(job_id, status="completed", result=None):
    conn = get_db()
    conn.execute(
        "UPDATE automation_jobs SET status = ?, result_json = ?, finished_at = ? WHERE id = ?",
        (status, json.dumps(result or {}), datetime.now().isoformat(), job_id)
    )
    conn.commit()
    conn.close()


def get_automation_jobs(limit=20):
    conn = get_db()
    rows = conn.execute(
        "SELECT * FROM automation_jobs ORDER BY created_at DESC LIMIT ?", (limit,)
    ).fetchall()
    conn.close()
    result = []
    for row in rows:
        d = dict(row)
        try:
            d["config"] = json.loads(d.get("config_json") or "{}")
        except (json.JSONDecodeError, TypeError):
            d["config"] = {}
        try:
            d["result"] = json.loads(d.get("result_json") or "{}")
        except (json.JSONDecodeError, TypeError):
            d["result"] = {}
        result.append(d)
    return result


# --- Funnel Analytics ---

def get_funnel_analytics():
    conn = get_db()
    analytics = {}

    analytics["pipeline_counts"] = {}
    for stage in PIPELINE_STAGES:
        count = conn.execute("SELECT COUNT(*) FROM leads WHERE status = ?", (stage,)).fetchone()[0]
        analytics["pipeline_counts"][stage] = count

    total = conn.execute("SELECT COUNT(*) FROM leads").fetchone()[0]
    analytics["total_leads"] = total

    analytics["conversion_rates"] = {}
    if total > 0:
        contacted = analytics["pipeline_counts"].get("contacted", 0)
        responded = analytics["pipeline_counts"].get("responded", 0)
        qualified = analytics["pipeline_counts"].get("qualified", 0)
        proposal = analytics["pipeline_counts"].get("proposal", 0)
        won = analytics["pipeline_counts"].get("won", 0)

        all_past_new = total - analytics["pipeline_counts"].get("new", 0)
        analytics["conversion_rates"]["new_to_contacted"] = round((all_past_new / total) * 100, 1) if total else 0
        analytics["conversion_rates"]["contacted_to_responded"] = round((responded / max(contacted + responded + qualified + proposal + won, 1)) * 100, 1)
        analytics["conversion_rates"]["responded_to_qualified"] = round((qualified / max(responded + qualified + proposal + won, 1)) * 100, 1)
        analytics["conversion_rates"]["qualified_to_won"] = round((won / max(qualified + proposal + won, 1)) * 100, 1)
        analytics["conversion_rates"]["overall"] = round((won / total) * 100, 1)

    if table_exists(conn, "email_log"):
        analytics["emails_sent"] = conn.execute("SELECT COUNT(*) FROM email_log").fetchone()[0]
        if isinstance(conn, PGConnection):
            analytics["emails_today"] = conn.execute(
                "SELECT COUNT(*) FROM email_log WHERE sent_at::date >= CURRENT_DATE"
            ).fetchone()[0]
            analytics["emails_this_week"] = conn.execute(
                "SELECT COUNT(*) FROM email_log WHERE sent_at::date >= CURRENT_DATE - INTERVAL '7 days'"
            ).fetchone()[0]
            analytics["emails_by_day"] = []
            for row in conn.execute(
                "SELECT sent_at::date as day, COUNT(*) as cnt FROM email_log WHERE sent_at::date >= CURRENT_DATE - INTERVAL '30 days' GROUP BY sent_at::date ORDER BY day"
            ).fetchall():
                analytics["emails_by_day"].append({"day": str(row[0]), "count": row[1]})
        else:
            analytics["emails_today"] = conn.execute(
                "SELECT COUNT(*) FROM email_log WHERE sent_at >= date('now')"
            ).fetchone()[0]
            analytics["emails_this_week"] = conn.execute(
                "SELECT COUNT(*) FROM email_log WHERE sent_at >= date('now', '-7 days')"
            ).fetchone()[0]
            analytics["emails_by_day"] = []
            for row in conn.execute(
                "SELECT date(sent_at) as day, COUNT(*) as cnt FROM email_log WHERE sent_at >= date('now', '-30 days') GROUP BY date(sent_at) ORDER BY day"
            ).fetchall():
                analytics["emails_by_day"].append({"day": row[0], "count": row[1]})
    else:
        analytics["emails_sent"] = 0
        analytics["emails_today"] = 0
        analytics["emails_this_week"] = 0
        analytics["emails_by_day"] = []

    if table_exists(conn, "campaigns"):
        campaigns = conn.execute(
            "SELECT name, campaign_key, total_sent, total_opened, total_replied FROM campaigns ORDER BY total_sent DESC LIMIT 10"
        ).fetchall()
        analytics["campaign_performance"] = [dict(row) for row in campaigns]
    else:
        analytics["campaign_performance"] = []

    analytics["leads_by_week"] = []
    if isinstance(conn, PGConnection):
        week_query = """
            SELECT TO_CHAR(date_found::date, 'IYYY-"W"IW') as week, COUNT(*) as cnt
            FROM leads WHERE date_found::date >= CURRENT_DATE - INTERVAL '90 days' AND date_found != ''
            GROUP BY week ORDER BY week
        """
    else:
        week_query = """
            SELECT strftime('%Y-W%W', date_found) as week, COUNT(*) as cnt
            FROM leads WHERE date_found >= date('now', '-90 days') AND date_found != ''
            GROUP BY week ORDER BY week
        """
    for row in conn.execute(week_query).fetchall():
        analytics["leads_by_week"].append({"week": row[0], "count": row[1]})

    analytics["avg_icp_score"] = conn.execute(
        "SELECT COALESCE(AVG(icp_score), 0) FROM leads WHERE icp_score > 0"
    ).fetchone()[0]

    analytics["score_distribution"] = {}
    for label, low, high in [("0-25", 0, 25), ("26-50", 26, 50), ("51-75", 51, 75), ("76-100", 76, 100)]:
        count = conn.execute(
            "SELECT COUNT(*) FROM leads WHERE icp_score >= ? AND icp_score <= ?", (low, high)
        ).fetchone()[0]
        analytics["score_distribution"][label] = count

    conn.close()
    return analytics


if __name__ == "__main__":
    init_db()
    print(f"Database initialized at {DB_PATH}")
