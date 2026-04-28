import sqlite3
import os
import json
from datetime import datetime, date

DB_PATH = os.environ.get("LEADGEN_DB_PATH") or os.path.join(os.path.dirname(os.path.abspath(__file__)), "leads.db")

ALLOWED_COLUMNS = {
    "business_name", "owner_name", "category", "business_type", "phone", "email",
    "address", "city", "state", "zip_code", "has_website", "website_url",
    "website_score", "has_social_media", "social_links", "marketing_score",
    "lead_score", "filing_date", "date_found", "source", "status", "notes",
    "priority", "contacted", "contact_date", "tags", "next_followup",
    "created_at", "updated_at",
}

PIPELINE_STAGES = ["new", "contacted", "responded", "qualified", "proposal", "won", "lost"]


def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


def init_db():
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

        CREATE INDEX IF NOT EXISTS idx_leads_state ON leads(state);
        CREATE INDEX IF NOT EXISTS idx_leads_city ON leads(city);
        CREATE INDEX IF NOT EXISTS idx_leads_category ON leads(category);
        CREATE INDEX IF NOT EXISTS idx_leads_status ON leads(status);
        CREATE INDEX IF NOT EXISTS idx_leads_has_website ON leads(has_website);
        CREATE INDEX IF NOT EXISTS idx_leads_date_found ON leads(date_found);
        CREATE INDEX IF NOT EXISTS idx_leads_lead_score ON leads(lead_score);
        CREATE INDEX IF NOT EXISTS idx_leads_priority ON leads(priority);
        CREATE INDEX IF NOT EXISTS idx_leads_phone ON leads(phone);
        CREATE INDEX IF NOT EXISTS idx_activities_lead ON activities(lead_id);
        CREATE INDEX IF NOT EXISTS idx_activities_created ON activities(created_at);
    """)

    cur = conn.execute("PRAGMA table_info(leads)")
    existing_cols = {row[1] for row in cur.fetchall()}
    for col, ddl in [
        ("lead_score", "ALTER TABLE leads ADD COLUMN lead_score INTEGER DEFAULT 50"),
        ("tags", "ALTER TABLE leads ADD COLUMN tags TEXT DEFAULT ''"),
        ("next_followup", "ALTER TABLE leads ADD COLUMN next_followup TEXT DEFAULT ''"),
    ]:
        if col not in existing_cols:
            try:
                conn.execute(ddl)
            except sqlite3.OperationalError:
                pass

    conn.commit()
    conn.close()


def _sanitize_keys(data):
    return {k: v for k, v in data.items() if k in ALLOWED_COLUMNS}


def _phone_digits(phone):
    return "".join(c for c in (phone or "") if c.isdigit())


def add_lead(lead_data, dedupe_by_phone=True):
    conn = get_db()
    biz_name = (lead_data.get("business_name") or "").strip()
    if not biz_name:
        conn.close()
        return None

    city = (lead_data.get("city") or "").strip()
    state = (lead_data.get("state") or "").strip()
    phone_digits = _phone_digits(lead_data.get("phone", ""))

    existing = conn.execute(
        "SELECT id FROM leads WHERE LOWER(business_name) = LOWER(?) AND LOWER(city) = LOWER(?) AND state = ?",
        (biz_name, city, state)
    ).fetchone()
    if existing:
        conn.close()
        return None

    if dedupe_by_phone and phone_digits and len(phone_digits) >= 10:
        existing = conn.execute(
            "SELECT id FROM leads WHERE REPLACE(REPLACE(REPLACE(REPLACE(phone, '(', ''), ')', ''), ' ', ''), '-', '') LIKE ?",
            (f"%{phone_digits[-10:]}",)
        ).fetchone()
        if existing:
            conn.close()
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
    conn.close()
    return lead_id


def add_leads_bulk(leads_list):
    added = 0
    for lead in leads_list:
        result = add_lead(dict(lead))
        if result:
            added += 1
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

    allowed_sorts = {"date_found", "business_name", "city", "state", "lead_score", "marketing_score", "priority", "created_at", "category"}
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
            query += " AND (business_name LIKE ? OR owner_name LIKE ? OR notes LIKE ? OR phone LIKE ?)"
            s = f"%{filters['search']}%"
            params.extend([s, s, s, s])
        if filters.get("category"):
            query += " AND category LIKE ?"
            params.append(f"%{filters['category']}%")

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
    conn.close()


def delete_lead(lead_id):
    conn = get_db()
    conn.execute("DELETE FROM activities WHERE lead_id = ?", (lead_id,))
    conn.execute("DELETE FROM leads WHERE id = ?", (lead_id,))
    conn.commit()
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
    stats["new_today"] = conn.execute(
        "SELECT COUNT(*) FROM leads WHERE date_found = ?", (date.today().isoformat(),)
    ).fetchone()[0]
    stats["new_this_week"] = conn.execute(
        "SELECT COUNT(*) FROM leads WHERE date_found >= date('now', '-7 days')"
    ).fetchone()[0]
    stats["contacted"] = conn.execute("SELECT COUNT(*) FROM leads WHERE contacted = 1 OR status != 'new'").fetchone()[0]
    stats["high_priority"] = conn.execute("SELECT COUNT(*) FROM leads WHERE priority = 'high'").fetchone()[0]
    stats["needs_followup"] = conn.execute(
        "SELECT COUNT(*) FROM leads WHERE next_followup != '' AND next_followup <= ?",
        (date.today().isoformat(),)
    ).fetchone()[0]

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

    if stats["total"] > 0:
        stats["conversion_rate"] = round(
            (stats["by_status"].get("won", 0) / stats["total"]) * 100, 1
        )
        stats["contact_rate"] = round((stats["contacted"] / stats["total"]) * 100, 1)
    else:
        stats["conversion_rate"] = 0
        stats["contact_rate"] = 0

    conn.close()
    return stats


def get_pipeline_data():
    """Returns leads grouped by status for kanban view."""
    conn = get_db()
    pipeline = {}
    for stage in PIPELINE_STAGES:
        rows = conn.execute(
            "SELECT id, business_name, city, state, phone, priority, lead_score, category FROM leads WHERE status = ? ORDER BY lead_score DESC, date_found DESC LIMIT 100",
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
    """Update the live scrape status row used by the UI for progress polling."""
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
            if "," in val or '"' in val or "\n" in val:
                val = f'"{val}"'
            row.append(val)
        lines.append(",".join(row))
    return "\n".join(lines)


if __name__ == "__main__":
    init_db()
    print(f"Database initialized at {DB_PATH}")
