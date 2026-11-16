"""ApplyTrack API + frontend server.

Run:  ``uvicorn app.main:app --reload``  (or ``bash run.sh``)
Docs:  http://localhost:8000/docs  (FastAPI's built-in Swagger UI)

Routes
------
GET  /                              -> dashboard (static/index.html)
GET  /api/health
GET  /api/applications              -> list, ?status=&term=&q=&sort=
POST /api/applications              -> create (201)
GET  /api/applications/{id}        -> one application (404 if missing)
PUT  /api/applications/{id}        -> full replace (404 if missing)
DELETE /api/applications/{id}      -> delete (204)
DELETE /api/applications            -> delete ALL (used to clear sample data)
GET  /api/stats                     -> dashboard numbers
GET  /api/export/csv                -> all applications as CSV download
POST /api/import/csv                -> CSV upload, returns imported/skipped
GET  /api/applications/{id}/outreach
POST /api/applications/{id}/outreach
DELETE /api/outreach/{outreach_id}
"""

from __future__ import annotations

import csv
import io
from contextlib import asynccontextmanager
from datetime import date
from pathlib import Path

from fastapi import Depends, FastAPI, File, HTTPException, Query, UploadFile
from fastapi.responses import FileResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles

from app import database
from app.models import (
    ApplicationCreate,
    ApplicationOut,
    OutreachCreate,
    OutreachOut,
    Status,
)

STATIC_DIR = Path(__file__).resolve().parent.parent / "static"

SORT_COLUMNS = {
    "deadline": "deadline IS NULL, deadline ASC",
    "date_applied": "date_applied IS NULL, date_applied DESC",
    "company": "company ASC",
}


@asynccontextmanager
async def lifespan(_app: FastAPI):
    database.init_db()
    yield


app = FastAPI(title="ApplyTrack", version="1.0.0", lifespan=lifespan)
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def get_conn():
    conn = database.get_connection()
    try:
        yield conn
    finally:
        conn.close()


def _application_or_404(conn, app_id: int) -> dict:
    row = conn.execute(
        "SELECT * FROM applications WHERE id = ?", (app_id,)
    ).fetchone()
    if row is None:
        raise HTTPException(status_code=404, detail="Application not found")
    return database.row_to_dict(row)


def _with_outreach_count(conn, row: dict) -> dict:
    count = conn.execute(
        "SELECT COUNT(*) FROM outreach WHERE application_id = ?",
        (row["id"],),
    ).fetchone()[0]
    return {**row, "outreach_count": count}


def _insert_application(conn, data: ApplicationCreate) -> dict:
    cur = conn.execute(
        """
        INSERT INTO applications
            (company, role, location, term, req_id, date_applied,
             status, deadline, pay, notes, link)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            data.company,
            data.role,
            data.location,
            data.term,
            data.req_id,
            data.date_applied.isoformat() if data.date_applied else None,
            data.status.value,
            data.deadline.isoformat() if data.deadline else None,
            data.pay,
            data.notes,
            data.link,
        ),
    )
    conn.commit()
    return _application_or_404(conn, cur.lastrowid)


# ---------------------------------------------------------------------------
# Frontend + health
# ---------------------------------------------------------------------------

@app.get("/", include_in_schema=False)
def index():
    return FileResponse(STATIC_DIR / "index.html")


@app.get("/api/health")
def health():
    return {"status": "ok"}


# ---------------------------------------------------------------------------
# Stats + CSV (defined before /api/applications/{id} so the literal
# paths are not swallowed by the {id} route)
# ---------------------------------------------------------------------------

@app.get("/api/stats")
def stats(conn=Depends(get_conn)):
    return database.compute_stats(conn)


@app.get("/api/export/csv")
def export_csv(conn=Depends(get_conn)):
    """Download every application as a CSV file."""
    rows = conn.execute("SELECT * FROM applications ORDER BY id").fetchall()
    buf = io.StringIO()
    writer = csv.writer(buf)
    writer.writerow([
        "id", "company", "role", "location", "term", "req_id",
        "date_applied", "status", "deadline", "pay", "notes", "link",
    ])
    for r in rows:
        writer.writerow([
            r["id"], r["company"], r["role"], r["location"], r["term"],
            r["req_id"], r["date_applied"], r["status"], r["deadline"],
            r["pay"], r["notes"], r["link"],
        ])
    buf.seek(0)
    return StreamingResponse(
        iter([buf.getvalue()]),
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=applytrack.csv"},
    )


@app.post("/api/import/csv")
def import_csv(file: UploadFile = File(...), conn=Depends(get_conn)):
    """Upload a CSV in the export format. Bad rows are skipped, not fatal.

    Returns {"imported": n, "skipped": m, "errors": [...]}.

    NOTE: this is a plain ``def`` (not ``async def``) on purpose — the
    sqlite3 connection from the ``get_conn`` dependency is created on
    the thread that runs the endpoint, and an async endpoint would use
    it from the event-loop thread instead (sqlite3 raises
    ProgrammingError for cross-thread use).
    """
    if not file.filename or not file.filename.lower().endswith(".csv"):
        raise HTTPException(status_code=400, detail="Upload a .csv file")
    text = file.file.read().decode("utf-8-sig")
    reader = csv.DictReader(io.StringIO(text))
    imported, skipped, errors = 0, 0, []
    for line_no, row in enumerate(reader, start=2):
        try:
            data = ApplicationCreate(
                company=(row.get("company") or "").strip(),
                role=(row.get("role") or "").strip(),
                location=row.get("location") or None,
                term=row.get("term") or None,
                req_id=row.get("req_id") or None,
                date_applied=row.get("date_applied") or None,
                status=row.get("status") or "Applied",
                deadline=row.get("deadline") or None,
                pay=row.get("pay") or None,
                notes=row.get("notes") or None,
                link=row.get("link") or None,
            )
        except Exception as exc:  # validation error -> skip this row
            skipped += 1
            errors.append(f"Row {line_no}: {exc}")
            continue
        _insert_application(conn, data)
        imported += 1
    return {"imported": imported, "skipped": skipped, "errors": errors}


# ---------------------------------------------------------------------------
# Applications CRUD
# ---------------------------------------------------------------------------

@app.get("/api/applications", response_model=list[ApplicationOut])
def list_applications(
    status: Status | None = Query(default=None),
    term: str | None = Query(default=None),
    q: str | None = Query(default=None, description="Search company or role"),
    sort: str = Query(default="deadline",
                      pattern="^(deadline|date_applied|company)$"),
    conn=Depends(get_conn),
):
    """List applications, optionally filtered/searched/sorted.

    ``q`` matches company or role (case-insensitive, substring).
    ``sort=deadline`` puts applications with no deadline last.
    """
    sql = "SELECT * FROM applications WHERE 1=1"
    params: list = []
    if status is not None:
        sql += " AND status = ?"
        params.append(status.value)
    if term:
        sql += " AND term = ?"
        params.append(term)
    if q:
        sql += " AND (company LIKE ? OR role LIKE ?)"
        params.extend([f"%{q}%", f"%{q}%"])
    sql += f" ORDER BY {SORT_COLUMNS[sort]}, id ASC"
    rows = conn.execute(sql, params).fetchall()
    return [_with_outreach_count(conn, database.row_to_dict(r)) for r in rows]


@app.post("/api/applications", response_model=ApplicationOut, status_code=201)
def create_application(data: ApplicationCreate, conn=Depends(get_conn)):
    created = _insert_application(conn, data)
    return _with_outreach_count(conn, created)


@app.get("/api/applications/{app_id}", response_model=ApplicationOut)
def get_application(app_id: int, conn=Depends(get_conn)):
    row = _application_or_404(conn, app_id)
    return _with_outreach_count(conn, row)


@app.put("/api/applications/{app_id}", response_model=ApplicationOut)
def update_application(app_id: int, data: ApplicationCreate,
                       conn=Depends(get_conn)):
    _application_or_404(conn, app_id)  # 404 if missing
    conn.execute(
        """
        UPDATE applications SET
            company=?, role=?, location=?, term=?, req_id=?,
            date_applied=?, status=?, deadline=?, pay=?, notes=?, link=?,
            updated_at=datetime('now')
        WHERE id=?
        """,
        (
            data.company, data.role, data.location, data.term, data.req_id,
            data.date_applied.isoformat() if data.date_applied else None,
            data.status.value,
            data.deadline.isoformat() if data.deadline else None,
            data.pay, data.notes, data.link, app_id,
        ),
    )
    conn.commit()
    return _with_outreach_count(conn, _application_or_404(conn, app_id))


@app.delete("/api/applications/{app_id}", status_code=204)
def delete_application(app_id: int, conn=Depends(get_conn)):
    _application_or_404(conn, app_id)
    conn.execute("DELETE FROM applications WHERE id = ?", (app_id,))
    conn.commit()
    return None


@app.delete("/api/applications", status_code=204)
def delete_all_applications(conn=Depends(get_conn)):
    """Delete every application (and, via CASCADE, its outreach log).

    Used by the UI's "Clear all data" button to wipe the sample data.
    """
    conn.execute("DELETE FROM applications")
    conn.commit()
    return None


# ---------------------------------------------------------------------------
# Outreach log (per application)
# ---------------------------------------------------------------------------

@app.get("/api/applications/{app_id}/outreach",
         response_model=list[OutreachOut])
def list_outreach(app_id: int, conn=Depends(get_conn)):
    _application_or_404(conn, app_id)
    rows = conn.execute(
        "SELECT * FROM outreach WHERE application_id = ? ORDER BY date DESC, id DESC",
        (app_id,),
    ).fetchall()
    return [database.row_to_dict(r) for r in rows]


@app.post("/api/applications/{app_id}/outreach",
          response_model=OutreachOut, status_code=201)
def add_outreach(app_id: int, data: OutreachCreate, conn=Depends(get_conn)):
    _application_or_404(conn, app_id)
    day = data.date or date.today()
    cur = conn.execute(
        "INSERT INTO outreach (application_id, contact_name, date, channel, notes)"
        " VALUES (?, ?, ?, ?, ?)",
        (app_id, data.contact_name, day.isoformat(), data.channel.value,
         data.notes),
    )
    conn.commit()
    row = conn.execute(
        "SELECT * FROM outreach WHERE id = ?", (cur.lastrowid,)
    ).fetchone()
    return database.row_to_dict(row)


@app.delete("/api/outreach/{outreach_id}", status_code=204)
def delete_outreach(outreach_id: int, conn=Depends(get_conn)):
    row = conn.execute(
        "SELECT id FROM outreach WHERE id = ?", (outreach_id,)
    ).fetchone()
    if row is None:
        raise HTTPException(status_code=404, detail="Outreach entry not found")
    conn.execute("DELETE FROM outreach WHERE id = ?", (outreach_id,))
    conn.commit()
    return None
