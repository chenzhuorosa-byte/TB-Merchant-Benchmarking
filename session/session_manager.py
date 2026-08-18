"""
Manages scraping sessions using a local SQLite database (sessions.db).

Tables
------
sessions
    One row per scraping job. Tracks both Phase 1 (listing pages) and
    Phase 2 (detail pages) progress independently so either phase can
    be resumed after an interruption.

merchants
    One row per restaurant found during Phase 1.
    - listing_data  : JSON blob from the listing page card
    - detail_data   : JSON blob from the detail page (NULL until Phase 2)
    - detail_scraped: 0/1 flag — the resume checkpoint for Phase 2
"""

import json
import sqlite3
import uuid
from datetime import datetime


class SessionManager:

    def __init__(self, db_path="sessions.db"):
        self.db_path = db_path
        self._init_db()

    # ------------------------------------------------------------------
    # Setup
    # ------------------------------------------------------------------

    def _init_db(self):
        with self._connect() as conn:
            self._migrate(conn)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS sessions (
                    session_id              TEXT PRIMARY KEY,
                    primary_url             TEXT NOT NULL,
                    total_listing_pages     INTEGER NOT NULL DEFAULT 1,
                    last_listing_page       INTEGER NOT NULL DEFAULT 0,
                    selected_listing_fields TEXT NOT NULL DEFAULT '[]',
                    selected_detail_fields  TEXT NOT NULL DEFAULT '[]',
                    phase                   INTEGER NOT NULL DEFAULT 1,
                    status                  TEXT    NOT NULL DEFAULT 'running',
                    error_message           TEXT,
                    created_at              TEXT    NOT NULL
                )
            """)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS merchants (
                    id              INTEGER PRIMARY KEY AUTOINCREMENT,
                    session_id      TEXT    NOT NULL,
                    merchant_url    TEXT    NOT NULL,
                    listing_data    TEXT    NOT NULL DEFAULT '{}',
                    detail_data     TEXT,
                    detail_scraped  INTEGER NOT NULL DEFAULT 0,
                    FOREIGN KEY (session_id) REFERENCES sessions(session_id)
                )
            """)
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_merchants_session
                ON merchants(session_id, detail_scraped)
            """)

    def _migrate(self, conn):
        """
        Detect an outdated schema and rename it out of the way so the
        new schema can be created cleanly.

        The old schema (from the single-page scraper project) used columns
        'url', 'total_pages', 'selected_fields' in the sessions table.
        The new schema uses 'primary_url', 'total_listing_pages', etc.

        We simply rename the old sessions table to sessions_v1 (preserving
        the data) and let _init_db create the new one fresh.
        """
        tables = {r[0] for r in conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table'"
        ).fetchall()}

        if "sessions" in tables:
            old_cols = {r[1] for r in conn.execute("PRAGMA table_info(sessions)").fetchall()}
            # If the sessions table has the old column name, it needs migration
            if "url" in old_cols and "primary_url" not in old_cols:
                conn.execute("ALTER TABLE sessions RENAME TO sessions_v1")
                # Also rename scraped_rows if it exists (old table, no longer used)
                if "scraped_rows" in tables:
                    conn.execute("ALTER TABLE scraped_rows RENAME TO scraped_rows_v1")

    def _connect(self):
        return sqlite3.connect(self.db_path)

    # ------------------------------------------------------------------
    # Session CRUD
    # ------------------------------------------------------------------

    def create_session(self, primary_url, total_listing_pages,
                       selected_listing_fields, selected_detail_fields):
        """Create a new session and return its ID."""
        session_id = str(uuid.uuid4())[:8]
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO sessions
                    (session_id, primary_url, total_listing_pages,
                     selected_listing_fields, selected_detail_fields,
                     phase, status, created_at)
                VALUES (?, ?, ?, ?, ?, 1, 'running', ?)
                """,
                (
                    session_id,
                    primary_url,
                    total_listing_pages,
                    json.dumps(selected_listing_fields),
                    json.dumps(selected_detail_fields),
                    datetime.now().isoformat(timespec="seconds"),
                ),
            )
        return session_id

    def get_session(self, session_id):
        """Return the session as a dict, or None."""
        with self._connect() as conn:
            row = conn.execute(
                "SELECT * FROM sessions WHERE session_id = ?", (session_id,)
            ).fetchone()
        if row is None:
            return None
        return {
            "session_id":              row[0],
            "primary_url":             row[1],
            "total_listing_pages":     row[2],
            "last_listing_page":       row[3],
            "selected_listing_fields": json.loads(row[4]),
            "selected_detail_fields":  json.loads(row[5]),
            "phase":                   row[6],
            "status":                  row[7],
            "error_message":           row[8],
            "created_at":              row[9],
        }

    def list_sessions(self):
        """Return summary of all sessions, newest first."""
        with self._connect() as conn:
            rows = conn.execute(
                """
                SELECT s.session_id, s.primary_url, s.total_listing_pages,
                       s.last_listing_page, s.phase, s.status, s.created_at,
                       COUNT(m.id)                              AS total_merchants,
                       SUM(CASE WHEN m.detail_scraped=1 THEN 1 ELSE 0 END) AS done_merchants
                FROM sessions s
                LEFT JOIN merchants m ON m.session_id = s.session_id
                GROUP BY s.session_id
                ORDER BY s.created_at DESC
                """
            ).fetchall()
        return [
            {
                "session_id":          r[0],
                "primary_url":         r[1],
                "total_listing_pages": r[2],
                "last_listing_page":   r[3],
                "phase":               r[4],
                "status":              r[5],
                "created_at":          r[6],
                "total_merchants":     r[7] or 0,
                "done_merchants":      r[8] or 0,
            }
            for r in rows
        ]

    # ------------------------------------------------------------------
    # Phase 1 — listing page progress
    # ------------------------------------------------------------------

    def save_merchants_from_page(self, session_id, merchants):
        """
        Bulk-insert merchant records collected from one listing page.

        Each item in `merchants` is a dict:
            {"merchant_url": str, "listing_data": dict}
        """
        with self._connect() as conn:
            conn.executemany(
                """
                INSERT INTO merchants (session_id, merchant_url, listing_data)
                VALUES (?, ?, ?)
                """,
                [
                    (session_id, m["merchant_url"], json.dumps(m["listing_data"]))
                    for m in merchants
                ],
            )

    def update_listing_progress(self, session_id, page_num):
        """Advance the Phase 1 checkpoint after successfully scraping a page."""
        with self._connect() as conn:
            conn.execute(
                "UPDATE sessions SET last_listing_page = ? WHERE session_id = ?",
                (page_num, session_id),
            )

    def set_phase(self, session_id, phase):
        with self._connect() as conn:
            conn.execute(
                "UPDATE sessions SET phase = ? WHERE session_id = ?",
                (phase, session_id),
            )

    # ------------------------------------------------------------------
    # Phase 2 — detail page progress
    # ------------------------------------------------------------------

    def get_next_unscraped_merchant(self, session_id):
        """
        Return the next merchant that hasn't been detail-scraped yet,
        or None if all are done.
        """
        with self._connect() as conn:
            row = conn.execute(
                """
                SELECT id, merchant_url
                FROM merchants
                WHERE session_id = ? AND detail_scraped = 0
                ORDER BY id
                LIMIT 1
                """,
                (session_id,),
            ).fetchone()
        if row is None:
            return None
        return {"id": row[0], "merchant_url": row[1]}

    def update_merchant_detail(self, merchant_id, detail_data):
        """Save detail data for one merchant and mark it as scraped."""
        with self._connect() as conn:
            conn.execute(
                """
                UPDATE merchants
                SET detail_data = ?, detail_scraped = 1
                WHERE id = ?
                """,
                (json.dumps(detail_data), merchant_id),
            )

    def count_merchants(self, session_id):
        """Return (total, done) merchant counts for Phase 2 progress."""
        with self._connect() as conn:
            row = conn.execute(
                """
                SELECT COUNT(*),
                       SUM(CASE WHEN detail_scraped=1 THEN 1 ELSE 0 END)
                FROM merchants WHERE session_id = ?
                """,
                (session_id,),
            ).fetchone()
        return (row[0] or 0, row[1] or 0)

    # ------------------------------------------------------------------
    # Status
    # ------------------------------------------------------------------

    def set_status(self, session_id, status, error_message=None):
        with self._connect() as conn:
            conn.execute(
                "UPDATE sessions SET status = ?, error_message = ? WHERE session_id = ?",
                (status, error_message, session_id),
            )

    # ------------------------------------------------------------------
    # Export
    # ------------------------------------------------------------------

    def get_all_merchants(self, session_id):
        """
        Return every merchant row as a merged dict:
            {**listing_data, **detail_data, "merchant_url": ...}
        detail_data fields are empty strings if not yet scraped.
        """
        with self._connect() as conn:
            rows = conn.execute(
                """
                SELECT merchant_url, listing_data, detail_data
                FROM merchants
                WHERE session_id = ?
                ORDER BY id
                """,
                (session_id,),
            ).fetchall()

        result = []
        for merchant_url, listing_raw, detail_raw in rows:
            listing = json.loads(listing_raw) if listing_raw else {}
            detail  = json.loads(detail_raw)  if detail_raw  else {}
            merged  = {**listing, **detail}
            result.append(merged)
        return result
