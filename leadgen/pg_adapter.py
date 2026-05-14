"""
PostgreSQL adapter that mimics sqlite3 interface.

When DATABASE_URL is set, database.py uses this instead of sqlite3.
All existing SQL with ? parameters works unchanged — the adapter converts to %s.
"""

import os
import re

try:
    import psycopg2
    import psycopg2.extras
    HAS_PG = True
except ImportError:
    HAS_PG = False

DATABASE_URL = os.environ.get("DATABASE_URL", "")


def is_postgres():
    return bool(DATABASE_URL) and HAS_PG


class PGRow(dict):
    """Dict-like row that also supports index-based access like sqlite3.Row."""
    def __init__(self, data, columns):
        super().__init__(data)
        self._columns = columns

    def __getitem__(self, key):
        if isinstance(key, int):
            return super().__getitem__(self._columns[key])
        return super().__getitem__(key)

    def keys(self):
        return self._columns


class PGCursor:
    """Wraps psycopg2 cursor to return PGRow objects."""
    def __init__(self, cursor, last_id=None):
        self._cursor = cursor
        self._columns = []
        self._last_id = last_id

    def __iter__(self):
        if self._cursor.description:
            self._columns = [d[0] for d in self._cursor.description]
            for row in self._cursor:
                yield PGRow(row, self._columns)
        return

    @property
    def lastrowid(self):
        return self._last_id

    def fetchone(self):
        row = self._cursor.fetchone()
        if row and self._cursor.description:
            cols = [d[0] for d in self._cursor.description]
            return PGRow(row, cols)
        return row

    def fetchall(self):
        rows = self._cursor.fetchall()
        if rows and self._cursor.description:
            cols = [d[0] for d in self._cursor.description]
            return [PGRow(r, cols) for r in rows]
        return rows


def _convert_sql(sql):
    """Convert SQLite SQL to PostgreSQL-compatible SQL."""
    sql = sql.replace("?", "%s")
    sql = sql.replace("INTEGER PRIMARY KEY AUTOINCREMENT", "SERIAL PRIMARY KEY")
    sql = re.sub(r"TEXT DEFAULT CURRENT_TIMESTAMP", "TIMESTAMP DEFAULT NOW()", sql)
    if re.match(r"^\s*PRAGMA\b", sql, re.IGNORECASE):
        return "SELECT 1"
    sql = re.sub(r"date\('now',\s*'-(\d+) days'\)", r"CURRENT_DATE - INTERVAL '\1 days'", sql)
    sql = re.sub(r"date\('now'\)", "CURRENT_DATE", sql)
    sql = re.sub(
        r"INSERT\s+OR\s+IGNORE\s+INTO\s+(\S+)\s*\(([^)]+)\)\s*VALUES\s*\(([^)]+)\)",
        r"INSERT INTO \1 (\2) VALUES (\3) ON CONFLICT DO NOTHING",
        sql,
        flags=re.IGNORECASE,
    )
    return sql


class PGConnection:
    """PostgreSQL connection wrapper that mimics sqlite3 connection."""

    def __init__(self):
        self._conn = psycopg2.connect(
            DATABASE_URL,
            cursor_factory=psycopg2.extras.RealDictCursor,
        )
        self._conn.autocommit = False

    def execute(self, sql, params=None):
        sql = _convert_sql(sql)
        cursor = self._conn.cursor()
        last_id = None
        is_insert = sql.strip().upper().startswith("INSERT")
        if is_insert and "RETURNING" not in sql.upper():
            sql = sql.rstrip().rstrip(";") + " RETURNING id"
        try:
            cursor.execute(sql, params or ())
            if is_insert and cursor.description:
                row = cursor.fetchone()
                last_id = row.get("id") if row else None
        except psycopg2.Error:
            self._conn.rollback()
            raise
        return PGCursor(cursor, last_id=last_id)

    def executescript(self, sql):
        sql = _convert_sql(sql)
        statements = [s.strip() for s in sql.split(";") if s.strip()]
        cursor = self._conn.cursor()
        for stmt in statements:
            if not stmt or stmt.upper() in ("SELECT 1", "BEGIN", "COMMIT"):
                continue
            try:
                cursor.execute(stmt)
            except psycopg2.Error as e:
                self._conn.rollback()
                print(f"[PG] Warning: {str(e)[:100]}")
                continue
        self._conn.commit()

    def commit(self):
        self._conn.commit()

    def rollback(self):
        self._conn.rollback()

    def close(self):
        self._conn.close()

    @property
    def row_factory(self):
        return None

    @row_factory.setter
    def row_factory(self, value):
        pass  # psycopg2 uses RealDictCursor instead


def get_pg_connection():
    if not HAS_PG:
        raise ImportError("psycopg2 not installed. Run: pip install psycopg2-binary")
    return PGConnection()
