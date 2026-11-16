"""SQLite storage for ApplyTrack.

Deliberately plain ``sqlite3`` — no ORM. Every query is a visible,
parameterised SQL statement, so the whole data layer can be explained
in an interview line by line. The database file lives in ``data/`` by
default; set the ``APPLYTRACK_DB`` env var (tests do this) to point
somewhere else.
"""

from __future__ import annotations

import os
import sqlite3
from datetime import date
from pathlib import Path

DEFAULT_DB_PATH = Path(__file__).resolve().parent.parent / "data" / "applytrack.db"

STATUSES = ("Applied", "OA/Assessment", "Interview", "Offer", "Rejected")
# A "response" is any movement past the initial Applied state.
RESPONDED_STATUSES = ("OA/Assessment", "Interview", "Offer", "Rejected")


def db_path() -> Path:
    """Database location: env override, else ``data/applytrack.db``."""
    override = os.environ.get("APPLYTRACK_DB")
    return Path(override) if override else DEFAULT_DB_PATH


def get_connection(path: Path | None = None) -> sqlite3.Connection:
    """Open a connection with dict-like rows and foreign keys on."""
    conn = sqlite3.connect(path or db_path())
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def init_db(path: Path | None = None) -> Path:
    """Create the tables if they do not exist. Safe to call repeatedly."""
    target = Path(path) if path else db_path()
    target.parent.mkdir(parents=True, exist_ok=True)
    with get_connection(target) as conn:
        conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS applications (
                id            INTEGER PRIMARY KEY AUTOINCREMENT,
                company       TEXT NOT NULL,
                role          TEXT NOT NULL,
                location      TEXT,
                term          TEXT,
                req_id        TEXT,
                date_applied  TEXT,
                status        TEXT NOT NULL DEFAULT 'Applied'
                              CHECK (status IN
                                ('Applied','OA/Assessment','Interview','Offer','Rejected')),
                deadline      TEXT,
                pay           TEXT,
                notes         TEXT,
                link          TEXT,
                created_at    TEXT NOT NULL DEFAULT (datetime('now')),
                updated_at    TEXT NOT NULL DEFAULT (datetime('now'))
            );
            CREATE TABLE IF NOT EXISTS outreach (
                id              INTEGER PRIMARY KEY AUTOINCREMENT,
                application_id  INTEGER NOT NULL REFERENCES applications(id) ON DELETE CASCADE,
                contact_name    TEXT NOT NULL,
                date            TEXT NOT NULL,
                channel         TEXT NOT NULL DEFAULT 'Email'
                                CHECK (channel IN ('Email','LinkedIn','Phone','Other')),
                notes           TEXT,
                created_at      TEXT NOT NULL DEFAULT (datetime('now'))
            );
            CREATE INDEX IF NOT EXISTS idx_applications_status ON applications(status);
            CREATE INDEX IF NOT EXISTS idx_applications_deadline ON applications(deadline);
            CREATE INDEX IF NOT EXISTS idx_outreach_application ON outreach(application_id);
            """
        )
    return target


def row_to_dict(row: sqlite3.Row) -> dict:
    return dict(row)


# ---------------------------------------------------------------------------
# Stats
# ---------------------------------------------------------------------------

def compute_stats(conn: sqlite3.Connection, today: date | None = None) -> dict:
    """Dashboard numbers, computed with plain SQL + a little Python.

    response_rate = share of applications that got any response, i.e.
    moved out of "Applied" into OA/Assessment, Interview, Offer or
    Rejected. Upcoming deadlines = non-rejected applications whose
    deadline falls within the next 7 days (today included).
    """
    today = today or date.today()
    total = conn.execute("SELECT COUNT(*) FROM applications").fetchone()[0]

    by_status = {s: 0 for s in STATUSES}
    for row in conn.execute(
        "SELECT status, COUNT(*) AS n FROM applications GROUP BY status"
    ):
        by_status[row["status"]] = row["n"]

    responded = sum(by_status[s] for s in RESPONDED_STATUSES)
    response_rate = round(responded / total, 3) if total else 0.0

    upcoming = [
        row_to_dict(r)
        for r in conn.execute(
            """
            SELECT * FROM applications
            WHERE deadline IS NOT NULL
              AND deadline >= ?
              AND deadline <= date(?, '+7 days')
              AND status != 'Rejected'
            ORDER BY deadline ASC
            """,
            (today.isoformat(), today.isoformat()),
        )
    ]

    return {
        "total": total,
        "by_status": by_status,
        "response_rate": response_rate,
        "responded": responded,
        "upcoming_deadlines": upcoming,
        "upcoming_count": len(upcoming),
    }
