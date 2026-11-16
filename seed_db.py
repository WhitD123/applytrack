#!/usr/bin/env python3
"""Seed ApplyTrack with the 12 sample applications in app/seed_data.py.

Usage:
    python seed_db.py            # add sample rows (skips if DB already has data)
    python seed_db.py --force    # add them even if the DB is non-empty
    python seed_db.py --clear    # wipe ALL applications + outreach, then seed
    python seed_db.py --clear --no-seed   # wipe only, start empty

Run from the project root. Uses the same APPLYTRACK_DB env var as the app.
"""

from __future__ import annotations

import argparse

from app import database
from app.seed_data import sample_applications


def main() -> None:
    parser = argparse.ArgumentParser(description="Seed ApplyTrack sample data")
    parser.add_argument("--force", action="store_true",
                        help="Seed even if the database already has rows")
    parser.add_argument("--clear", action="store_true",
                        help="Delete all existing applications first")
    parser.add_argument("--no-seed", action="store_true",
                        help="With --clear: wipe only, do not re-seed")
    args = parser.parse_args()

    path = database.init_db()
    conn = database.get_connection(path)
    try:
        count = conn.execute("SELECT COUNT(*) FROM applications").fetchone()[0]
        if args.clear:
            conn.execute("DELETE FROM applications")
            conn.commit()
            count = 0
            print("Cleared all applications and outreach entries.")
        if args.no_seed:
            print(f"Database is now empty: {path}")
            return
        if count and not args.force:
            print(f"Database already has {count} application(s) — nothing seeded.")
            print("Use --force to add samples anyway, or --clear to start over.")
            return
        samples = sample_applications()
        for app_data in samples:
            conn.execute(
                """
                INSERT INTO applications
                    (company, role, location, term, req_id, date_applied,
                     status, deadline, pay, notes, link)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    app_data.company, app_data.role, app_data.location,
                    app_data.term, app_data.req_id,
                    app_data.date_applied.isoformat() if app_data.date_applied else None,
                    app_data.status.value,
                    app_data.deadline.isoformat() if app_data.deadline else None,
                    app_data.pay, app_data.notes, app_data.link,
                ),
            )
        conn.commit()
        total = conn.execute("SELECT COUNT(*) FROM applications").fetchone()[0]
        print(f"Seeded {len(samples)} sample applications ({total} total) into {path}")
    finally:
        conn.close()


if __name__ == "__main__":
    main()
