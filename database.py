"""
database.py — SQLite database operations for VerdictToValue
Schema: cases, review_queue, dashboard_items, audit_log
"""
import sqlite3
import json
import time
from datetime import datetime
from pathlib import Path
from typing import Optional, List, Dict, Any
from loguru import logger

from backend.config import DB_PATH


def get_connection() -> sqlite3.Connection:
    """Get a database connection with row factory for dict-like access."""
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")  # Better concurrent access
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


def init_db():
    """Initialize all database tables."""
    conn = get_connection()
    try:
        conn.executescript("""
        -- ── Uploaded files tracking ──────────────────────────────────────────
        CREATE TABLE IF NOT EXISTS uploaded_files (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            filename    TEXT NOT NULL,
            filepath    TEXT NOT NULL,
            file_size   INTEGER,
            status      TEXT DEFAULT 'processing',  -- processing|done|failed
            uploaded_at TEXT DEFAULT (datetime('now')),
            processed_at TEXT
        );

        -- ── Review queue: AI output awaiting human verification ──────────────
        CREATE TABLE IF NOT EXISTS review_queue (
            id                  INTEGER PRIMARY KEY AUTOINCREMENT,
            file_id             INTEGER REFERENCES uploaded_files(id),
            filename            TEXT,
            
            -- Case metadata
            case_number         TEXT,
            court               TEXT,
            judge               TEXT,
            date_of_judgment    TEXT,
            petitioner          TEXT,
            respondent          TEXT,
            
            -- AI analysis
            verdict             TEXT,    -- comply | appeal | review
            directive           TEXT,
            additional_directives TEXT,  -- JSON array
            deadline_value      INTEGER,
            deadline_unit       TEXT,
            deadline_raw        TEXT,
            deadline_notes      TEXT,
            department          TEXT,
            responsible_authority TEXT,
            amount_involved     TEXT,
            contempt_risk       INTEGER DEFAULT 0,
            urgency             TEXT DEFAULT 'medium',
            
            -- Explainability
            citation_text       TEXT,
            citation_location   TEXT,
            secondary_citations TEXT,    -- JSON array
            rationale           TEXT,
            confidence_score    REAL DEFAULT 0.75,
            keywords            TEXT,    -- JSON array
            
            -- Full extracted text (for display)
            raw_text_excerpt    TEXT,
            
            -- Review status
            review_status       TEXT DEFAULT 'pending',  -- pending|approved|rejected|edited
            reviewer_notes      TEXT,
            created_at          TEXT DEFAULT (datetime('now'))
        );

        -- ── Dashboard: only verified/approved items ───────────────────────────
        CREATE TABLE IF NOT EXISTS dashboard_items (
            id                  INTEGER PRIMARY KEY AUTOINCREMENT,
            review_id           INTEGER REFERENCES review_queue(id),
            filename            TEXT,
            
            -- Case metadata
            case_number         TEXT,
            court               TEXT,
            judge               TEXT,
            date_of_judgment    TEXT,
            petitioner          TEXT,
            respondent          TEXT,
            
            -- Action plan (human-verified)
            verdict             TEXT,
            directive           TEXT,
            additional_directives TEXT,
            deadline_value      INTEGER,
            deadline_unit       TEXT,
            deadline_raw        TEXT,
            deadline_notes      TEXT,
            department          TEXT,
            responsible_authority TEXT,
            amount_involved     TEXT,
            contempt_risk       INTEGER DEFAULT 0,
            urgency             TEXT,
            
            -- Explainability
            citation_text       TEXT,
            citation_location   TEXT,
            secondary_citations TEXT,
            rationale           TEXT,
            confidence_score    REAL,
            keywords            TEXT,
            reviewer_notes      TEXT,
            
            -- Timestamps
            approved_at         TEXT DEFAULT (datetime('now')),
            
            -- Computed deadline date (ISO)
            deadline_date       TEXT
        );

        -- ── Audit log ─────────────────────────────────────────────────────────
        CREATE TABLE IF NOT EXISTS audit_log (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            action      TEXT NOT NULL,   -- uploaded|processed|approved|rejected|edited|exported
            item_id     INTEGER,
            item_type   TEXT,            -- review|dashboard|file
            details     TEXT,            -- JSON
            created_at  TEXT DEFAULT (datetime('now'))
        );
        """)
        conn.commit()
        logger.info(f"Database initialized at {DB_PATH}")
    finally:
        conn.close()


# ── Uploaded Files ─────────────────────────────────────────────────────────────

def create_file_record(filename: str, filepath: str, file_size: int) -> int:
    conn = get_connection()
    try:
        cur = conn.execute(
            "INSERT INTO uploaded_files (filename, filepath, file_size, status) VALUES (?,?,?,?)",
            (filename, filepath, file_size, "processing")
        )
        conn.commit()
        return cur.lastrowid
    finally:
        conn.close()


def update_file_status(file_id: int, status: str):
    conn = get_connection()
    try:
        conn.execute(
            "UPDATE uploaded_files SET status=?, processed_at=datetime('now') WHERE id=?",
            (status, file_id)
        )
        conn.commit()
    finally:
        conn.close()


# ── Review Queue ───────────────────────────────────────────────────────────────

def insert_review_item(data: dict) -> int:
    """Insert AI-analyzed case into review queue."""
    conn = get_connection()
    try:
        cur = conn.execute("""
            INSERT INTO review_queue (
                file_id, filename,
                case_number, court, judge, date_of_judgment, petitioner, respondent,
                verdict, directive, additional_directives,
                deadline_value, deadline_unit, deadline_raw, deadline_notes,
                department, responsible_authority, amount_involved,
                contempt_risk, urgency,
                citation_text, citation_location, secondary_citations,
                rationale, confidence_score, keywords, raw_text_excerpt
            ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
        """, (
            data.get("file_id"),
            data.get("filename", ""),
            data.get("case_number", ""),
            data.get("court", ""),
            data.get("judge", ""),
            data.get("date_of_judgment", ""),
            data.get("petitioner", ""),
            data.get("respondent", ""),
            data.get("verdict", "review"),
            data.get("directive", ""),
            json.dumps(data.get("additional_directives", [])),
            data.get("deadline_value"),
            data.get("deadline_unit", "days"),
            data.get("deadline_raw", ""),
            data.get("deadline_notes", ""),
            data.get("department", "General Administration"),
            data.get("responsible_authority", ""),
            data.get("amount_involved", ""),
            1 if data.get("contempt_risk") else 0,
            data.get("urgency", "medium"),
            data.get("citation_text", ""),
            data.get("citation_location", ""),
            json.dumps(data.get("secondary_citations", [])),
            data.get("rationale", ""),
            data.get("confidence_score", 0.75),
            json.dumps(data.get("keywords", [])),
            data.get("raw_text_excerpt", ""),
        ))
        conn.commit()
        _audit(conn, "processed", cur.lastrowid, "review", {"case": data.get("case_number")})
        return cur.lastrowid
    finally:
        conn.close()


def get_review_items(status: str = "pending") -> List[Dict]:
    conn = get_connection()
    try:
        rows = conn.execute(
            "SELECT * FROM review_queue WHERE review_status=? ORDER BY created_at DESC",
            (status,)
        ).fetchall()
        return [_row_to_dict(r) for r in rows]
    finally:
        conn.close()


def get_review_item(item_id: int) -> Optional[Dict]:
    conn = get_connection()
    try:
        row = conn.execute("SELECT * FROM review_queue WHERE id=?", (item_id,)).fetchone()
        return _row_to_dict(row) if row else None
    finally:
        conn.close()


def approve_review_item(item_id: int, edits: Optional[dict] = None, reviewer_notes: str = "") -> int:
    """Approve a review item, optionally with edits. Returns new dashboard item id."""
    conn = get_connection()
    try:
        row = conn.execute("SELECT * FROM review_queue WHERE id=?", (item_id,)).fetchone()
        if not row:
            raise ValueError(f"Review item {item_id} not found")

        data = _row_to_dict(row)

        # Apply human edits
        if edits:
            for k, v in edits.items():
                if k in data:
                    data[k] = v

        # Compute deadline date
        deadline_date = _compute_deadline_date(data.get("deadline_value"), data.get("deadline_unit"))

        # Insert to dashboard
        cur = conn.execute("""
            INSERT INTO dashboard_items (
                review_id, filename,
                case_number, court, judge, date_of_judgment, petitioner, respondent,
                verdict, directive, additional_directives,
                deadline_value, deadline_unit, deadline_raw, deadline_notes,
                department, responsible_authority, amount_involved,
                contempt_risk, urgency,
                citation_text, citation_location, secondary_citations,
                rationale, confidence_score, keywords,
                reviewer_notes, deadline_date
            ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
        """, (
            item_id,
            data.get("filename", ""),
            data.get("case_number", ""),
            data.get("court", ""),
            data.get("judge", ""),
            data.get("date_of_judgment", ""),
            data.get("petitioner", ""),
            data.get("respondent", ""),
            data.get("verdict", "review"),
            data.get("directive", ""),
            data.get("additional_directives", "[]"),
            data.get("deadline_value"),
            data.get("deadline_unit", "days"),
            data.get("deadline_raw", ""),
            data.get("deadline_notes", ""),
            data.get("department", ""),
            data.get("responsible_authority", ""),
            data.get("amount_involved", ""),
            data.get("contempt_risk", 0),
            data.get("urgency", "medium"),
            data.get("citation_text", ""),
            data.get("citation_location", ""),
            data.get("secondary_citations", "[]"),
            data.get("rationale", ""),
            data.get("confidence_score", 0.75),
            data.get("keywords", "[]"),
            reviewer_notes,
            deadline_date,
        ))
        dashboard_id = cur.lastrowid

        # Mark review item as approved
        conn.execute(
            "UPDATE review_queue SET review_status='approved', reviewer_notes=? WHERE id=?",
            (reviewer_notes, item_id)
        )
        conn.commit()
        _audit(conn, "approved", item_id, "review", {"dashboard_id": dashboard_id})
        return dashboard_id
    finally:
        conn.close()


def reject_review_item(item_id: int, reason: str = ""):
    conn = get_connection()
    try:
        conn.execute(
            "UPDATE review_queue SET review_status='rejected', reviewer_notes=? WHERE id=?",
            (reason, item_id)
        )
        conn.commit()
        _audit(conn, "rejected", item_id, "review", {"reason": reason})
    finally:
        conn.close()


# ── Dashboard ──────────────────────────────────────────────────────────────────

def get_dashboard_items(
    department: Optional[str] = None,
    urgency: Optional[str] = None,
    verdict: Optional[str] = None,
    search: Optional[str] = None,
) -> List[Dict]:
    conn = get_connection()
    try:
        query = "SELECT * FROM dashboard_items WHERE 1=1"
        params = []
        if department:
            query += " AND department=?"
            params.append(department)
        if urgency:
            query += " AND urgency=?"
            params.append(urgency)
        if verdict:
            query += " AND verdict=?"
            params.append(verdict)
        if search:
            query += " AND (case_number LIKE ? OR directive LIKE ? OR petitioner LIKE ?)"
            s = f"%{search}%"
            params += [s, s, s]
        query += " ORDER BY approved_at DESC"
        rows = conn.execute(query, params).fetchall()
        return [_row_to_dict(r) for r in rows]
    finally:
        conn.close()


def get_dashboard_stats() -> Dict:
    conn = get_connection()
    try:
        total = conn.execute("SELECT COUNT(*) FROM dashboard_items").fetchone()[0]
        by_verdict = {
            r[0]: r[1]
            for r in conn.execute(
                "SELECT verdict, COUNT(*) FROM dashboard_items GROUP BY verdict"
            ).fetchall()
        }
        by_urgency = {
            r[0]: r[1]
            for r in conn.execute(
                "SELECT urgency, COUNT(*) FROM dashboard_items GROUP BY urgency"
            ).fetchall()
        }
        by_dept = {
            r[0]: r[1]
            for r in conn.execute(
                "SELECT department, COUNT(*) FROM dashboard_items GROUP BY department ORDER BY COUNT(*) DESC LIMIT 7"
            ).fetchall()
        }
        pending_review = conn.execute(
            "SELECT COUNT(*) FROM review_queue WHERE review_status='pending'"
        ).fetchone()[0]
        contempt_risk = conn.execute(
            "SELECT COUNT(*) FROM dashboard_items WHERE contempt_risk=1"
        ).fetchone()[0]
        return {
            "total": total,
            "pending_review": pending_review,
            "contempt_risk": contempt_risk,
            "by_verdict": by_verdict,
            "by_urgency": by_urgency,
            "by_department": by_dept,
        }
    finally:
        conn.close()


# ── Helpers ────────────────────────────────────────────────────────────────────

def _row_to_dict(row) -> Dict:
    """Convert sqlite3.Row to dict, parsing JSON fields."""
    if row is None:
        return {}
    d = dict(row)
    for field in ["additional_directives", "secondary_citations", "keywords"]:
        if field in d and d[field]:
            try:
                d[field] = json.loads(d[field])
            except (json.JSONDecodeError, TypeError):
                d[field] = []
    return d


def _compute_deadline_date(value: Optional[int], unit: Optional[str]) -> Optional[str]:
    """Compute actual deadline date from value+unit."""
    if not value or not unit:
        return None
    from datetime import datetime, timedelta
    days_map = {"days": 1, "day": 1, "weeks": 7, "week": 7, "months": 30, "month": 30}
    multiplier = days_map.get(unit.lower(), 1)
    delta = timedelta(days=value * multiplier)
    return (datetime.now() + delta).strftime("%d %b %Y")


def _audit(conn: sqlite3.Connection, action: str, item_id: int, item_type: str, details: dict):
    try:
        conn.execute(
            "INSERT INTO audit_log (action, item_id, item_type, details) VALUES (?,?,?,?)",
            (action, item_id, item_type, json.dumps(details))
        )
    except Exception:
        pass  # Audit failure should not break main flow
