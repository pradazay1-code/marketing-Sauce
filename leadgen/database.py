import sqlite3
import os
from datetime import datetime, date

DB_PATH = os.path.join(os.path.dirname(__file__), "leads.db")

ALLOWED_COLUMNS = {
    "business_name", "owner_name", "category", "business_type", "phone", "email",
    "address", "city", "state", "zip_code", "has_website", "website_url",
    "website_score", "has_social_media", "social_links", "marketing_score",
    "filing_date", "date_found", "source", "status", "notes", "priority",
    "contacted", "contact_date", "created_at", "updated_at",
}


def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
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
            filing_date TEXT DEFAULT '',
            date_found TEXT DEFAULT '',
            source TEXT DEFAULT '',
            status TEXT DEFAULT 'new',
            notes TEXT DEFAULT '',
            priority TEXT DEFAULT 'medium',
            contacted INTEGER DEFAULT 0,
            contact_date TEXT DEFAULT '',
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            updated_at TEXT DEFAULT CURRENT_TIMESTAMP
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
        CREATE INDEX IF NOT EXISTS idx_leads_marketing_score ON leads(marketing_score);
        CREATE INDEX IF NOT EXISTS idx_leads_priority ON leads(priority);
    """)
    conn.commit()
    conn.close()


def _sanitize_keys(data):
    return {k: v for k, v in data.items() if k in ALLOWED_COLUMNS}


def add_lead(lead_data):
    conn = get_db()
    biz_name = (lead_data.get("business_name") or "").strip()
    city = (lead_data.get("city") or "").strip()
    state = (lead_data.get("state") or "").strip()

    existing = conn.execute(
        "SELECT id FROM leads WHERE LOWER(business_name) = LOWER(?) AND LOWER(city) = LOWER(?) AND state = ?",
        (biz_name, city, state)
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
        if filters.get("search"):
            query += " AND (business_name LIKE ? OR owner_name LIKE ? OR notes LIKE ? OR phone LIKE ?)"
            s = f"%{filters['search']}%"
            params.extend([s, s, s, s])
        if filters.get("min_score") is not None:
            query += " AND marketing_score <= ?"
            params.append(int(filters["min_score"]))
        if filters.get("date_from"):
            query += " AND date_found >= ?"
            params.append(filters["date_from"])
        if filters.get("date_to"):
            query += " AND date_found <= ?"
            params.append(filters["date_to"])

    allowed_sorts = {"date_found", "business_name", "city", "state", "marketing_score", "priority", "created_at", "category"}
    if sort_by not in allowed_sorts:
        sort_by = "date_found"
    sort_dir = "ASC" if sort_dir.upper() == "ASC" else "DESC"
    query += f" ORDER BY {sort_by} {sort_dir} LIMIT ? OFFSET ?"
    params.extend([limit, offset])

    rows = conn.execute(query, params).fetchall()
    conn.close()
    return [dict(row) for row in rows]


def get_lead_by_id(lead_id):
    conn = get_db()
    row = conn.execute("SELECT * FROM leads WHERE id = ?", (lead_id,)).fetchone()
    conn.close()
    return dict(row) if row else None


def update_lead(lead_id, updates):
    safe_updates = _sanitize_keys(updates)
    if not safe_updates:
        return
    conn = get_db()
    safe_updates["updated_at"] = datetime.now().isoformat()
    set_clause = ", ".join([f"{k} = ?" for k in safe_updates.keys()])
    values = list(safe_updates.values()) + [lead_id]
    conn.execute(f"UPDATE leads SET {set_clause} WHERE id = ?", values)
    conn.commit()
    conn.close()


def delete_lead(lead_id):
    conn = get_db()
    conn.execute("DELETE FROM leads WHERE id = ?", (lead_id,))
    conn.commit()
    conn.close()


def get_stats():
    conn = get_db()
    stats = {}
    stats["total"] = conn.execute("SELECT COUNT(*) FROM leads").fetchone()[0]
    stats["no_website"] = conn.execute("SELECT COUNT(*) FROM leads WHERE has_website = 0").fetchone()[0]
    stats["new_today"] = conn.execute(
        "SELECT COUNT(*) FROM leads WHERE date_found = ?", (date.today().isoformat(),)
    ).fetchone()[0]
    stats["contacted"] = conn.execute("SELECT COUNT(*) FROM leads WHERE contacted = 1").fetchone()[0]
    stats["high_priority"] = conn.execute("SELECT COUNT(*) FROM leads WHERE priority = 'high'").fetchone()[0]
    stats["by_state"] = {}
    for row in conn.execute("SELECT state, COUNT(*) as cnt FROM leads WHERE state != '' GROUP BY state ORDER BY cnt DESC"):
        stats["by_state"][row[0]] = row[1]
    stats["by_category"] = {}
    for row in conn.execute("SELECT category, COUNT(*) as cnt FROM leads WHERE category != '' GROUP BY category ORDER BY cnt DESC LIMIT 10"):
        stats["by_category"][row[0]] = row[1]
    stats["by_priority"] = {}
    for row in conn.execute("SELECT priority, COUNT(*) as cnt FROM leads GROUP BY priority"):
        stats["by_priority"][row[0]] = row[1]
    conn.close()
    return stats


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


def export_csv(filters=None):
    leads = get_leads(filters=filters, limit=10000)
    if not leads:
        return ""
    headers = ["business_name", "owner_name", "category", "business_type", "phone", "email",
               "address", "city", "state", "has_website", "website_url", "marketing_score",
               "priority", "status", "date_found", "source", "notes"]
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
