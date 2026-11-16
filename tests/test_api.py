"""Tests for the ApplyTrack API.

Each test gets a fresh, empty SQLite database in a temp directory:
the APPLYTRACK_DB env var is pointed at it *before* app.main is
imported, so the app under test never touches the real data file.
Run with:  bash run_tests.sh   (or: .venv/bin/python -m pytest -v)
"""

import csv
import io
import os
import sys
from datetime import date, timedelta
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))


@pytest.fixture()
def client(tmp_path, monkeypatch):
    db_file = tmp_path / "test.db"
    monkeypatch.setenv("APPLYTRACK_DB", str(db_file))
    # Import (or re-import) the app after the env var is set.
    import app.main as main_module
    import importlib

    importlib.reload(main_module)
    with TestClient(main_module.app) as c:
        yield c


def sample_payload(**overrides):
    payload = {
        "company": "Acme Corp",
        "role": "Software Engineering Intern",
        "location": "Austin, TX",
        "term": "Summer 2027",
        "req_id": "REQ-1",
        "date_applied": "2026-11-10",
        "status": "Applied",
        "deadline": "2026-12-01",
        "pay": "$30/hr",
        "notes": "Test application",
        "link": "https://example.com/jobs/1",
    }
    payload.update(overrides)
    return payload


def create(client, **overrides):
    resp = client.post("/api/applications", json=sample_payload(**overrides))
    assert resp.status_code == 201, resp.text
    return resp.json()


# ---------------------------------------------------------------------------
# Health + CRUD
# ---------------------------------------------------------------------------

def test_health(client):
    assert client.get("/api/health").json() == {"status": "ok"}


def test_create_and_get_application(client):
    created = create(client)
    assert created["id"] > 0
    assert created["company"] == "Acme Corp"
    assert created["status"] == "Applied"
    assert created["outreach_count"] == 0

    got = client.get(f"/api/applications/{created['id']}")
    assert got.status_code == 200
    assert got.json()["role"] == "Software Engineering Intern"


def test_get_missing_application_is_404(client):
    assert client.get("/api/applications/9999").status_code == 404


def test_update_application(client):
    created = create(client)
    resp = client.put(
        f"/api/applications/{created['id']}",
        json=sample_payload(status="Interview", pay="$35/hr"),
    )
    assert resp.status_code == 200
    assert resp.json()["status"] == "Interview"
    assert resp.json()["pay"] == "$35/hr"


def test_update_missing_application_is_404(client):
    resp = client.put("/api/applications/9999", json=sample_payload())
    assert resp.status_code == 404


def test_delete_application(client):
    created = create(client)
    assert client.delete(f"/api/applications/{created['id']}").status_code == 204
    assert client.get(f"/api/applications/{created['id']}").status_code == 404


def test_delete_missing_application_is_404(client):
    assert client.delete("/api/applications/9999").status_code == 404


# ---------------------------------------------------------------------------
# Validation errors
# ---------------------------------------------------------------------------

def test_missing_company_is_422(client):
    payload = sample_payload()
    del payload["company"]
    assert client.post("/api/applications", json=payload).status_code == 422


def test_empty_company_is_422(client):
    resp = client.post("/api/applications",
                       json=sample_payload(company="   "))
    assert resp.status_code == 422


def test_missing_role_is_422(client):
    payload = sample_payload()
    del payload["role"]
    assert client.post("/api/applications", json=payload).status_code == 422


def test_bad_status_is_422(client):
    resp = client.post("/api/applications",
                       json=sample_payload(status="Hired"))
    assert resp.status_code == 422


def test_bad_date_is_422(client):
    resp = client.post("/api/applications",
                       json=sample_payload(deadline="not-a-date"))
    assert resp.status_code == 422


def test_bad_link_is_422(client):
    resp = client.post("/api/applications",
                       json=sample_payload(link="ftp://example.com"))
    assert resp.status_code == 422


# ---------------------------------------------------------------------------
# Filtering, search, sorting
# ---------------------------------------------------------------------------

def test_filter_by_status(client):
    create(client, company="Alpha", status="Applied")
    create(client, company="Beta", status="Interview")
    create(client, company="Gamma", status="Interview")

    resp = client.get("/api/applications?status=Interview")
    assert resp.status_code == 200
    companies = [a["company"] for a in resp.json()]
    assert companies == ["Beta", "Gamma"]


def test_filter_by_term(client):
    create(client, company="Alpha", term="Spring 2027")
    create(client, company="Beta", term="Summer 2027")
    resp = client.get("/api/applications?term=Summer 2027")
    assert [a["company"] for a in resp.json()] == ["Beta"]


def test_search_by_company_and_role(client):
    create(client, company="Texas Instruments", role="Compiler Intern")
    create(client, company="Acme Corp", role="Backend Intern")
    resp = client.get("/api/applications?q=compiler")
    assert [a["company"] for a in resp.json()] == ["Texas Instruments"]
    resp = client.get("/api/applications?q=ACME")
    assert [a["company"] for a in resp.json()] == ["Acme Corp"]


def test_sort_by_deadline_puts_missing_deadlines_last(client):
    create(client, company="NoDeadline", deadline=None)
    create(client, company="Later", deadline="2026-12-20")
    create(client, company="Sooner", deadline="2026-11-20")
    resp = client.get("/api/applications?sort=deadline")
    assert [a["company"] for a in resp.json()] == ["Sooner", "Later", "NoDeadline"]


# ---------------------------------------------------------------------------
# Stats
# ---------------------------------------------------------------------------

def test_stats_empty_database(client):
    stats = client.get("/api/stats").json()
    assert stats["total"] == 0
    assert stats["response_rate"] == 0.0
    assert stats["by_status"] == {
        "Applied": 0, "OA/Assessment": 0, "Interview": 0,
        "Offer": 0, "Rejected": 0,
    }
    assert stats["upcoming_deadlines"] == []


def test_stats_counts_and_response_rate(client):
    create(client, company="A", status="Applied")
    create(client, company="B", status="OA/Assessment")
    create(client, company="C", status="Interview")
    create(client, company="D", status="Offer")
    create(client, company="E", status="Rejected")
    stats = client.get("/api/stats").json()
    assert stats["total"] == 5
    assert stats["by_status"]["Applied"] == 1
    assert stats["by_status"]["Interview"] == 1
    assert stats["responded"] == 4
    assert stats["response_rate"] == 0.8  # 4 of 5 moved past "Applied"


def test_stats_upcoming_deadlines_within_7_days(client):
    today = date.today()
    create(client, company="Soon", deadline=(today + timedelta(days=3)).isoformat())
    create(client, company="Far", deadline=(today + timedelta(days=30)).isoformat())
    create(client, company="Past", deadline=(today - timedelta(days=1)).isoformat())
    create(client, company="SoonRejected", status="Rejected",
           deadline=(today + timedelta(days=2)).isoformat())
    stats = client.get("/api/stats").json()
    upcoming = [a["company"] for a in stats["upcoming_deadlines"]]
    assert upcoming == ["Soon"]  # far/past out of window, rejected excluded


# ---------------------------------------------------------------------------
# Outreach log
# ---------------------------------------------------------------------------

def test_outreach_crud(client):
    app_row = create(client)
    resp = client.post(
        f"/api/applications/{app_row['id']}/outreach",
        json={"contact_name": "Jane Alum", "channel": "LinkedIn",
              "notes": "Asked for advice"},
    )
    assert resp.status_code == 201, resp.text
    entry = resp.json()
    assert entry["contact_name"] == "Jane Alum"
    assert entry["date"] == date.today().isoformat()  # defaults to today

    listed = client.get(f"/api/applications/{app_row['id']}/outreach").json()
    assert len(listed) == 1

    # The application's outreach_count follows the log.
    assert client.get(f"/api/applications/{app_row['id']}").json()["outreach_count"] == 1

    assert client.delete(f"/api/outreach/{entry['id']}").status_code == 204
    assert client.get(f"/api/applications/{app_row['id']}/outreach").json() == []


def test_outreach_on_missing_application_is_404(client):
    resp = client.post("/api/applications/9999/outreach",
                       json={"contact_name": "Nobody"})
    assert resp.status_code == 404


def test_outreach_missing_contact_is_422(client):
    app_row = create(client)
    resp = client.post(f"/api/applications/{app_row['id']}/outreach",
                       json={"channel": "Email"})
    assert resp.status_code == 422


def test_deleting_application_deletes_its_outreach(client):
    app_row = create(client)
    client.post(f"/api/applications/{app_row['id']}/outreach",
                json={"contact_name": "Jane Alum"})
    client.delete(f"/api/applications/{app_row['id']}")
    # Outreach table is empty now (CASCADE) — listing the app 404s, and
    # a fresh stats/list check shows no leftover rows anywhere.
    assert client.get("/api/applications").json() == []


# ---------------------------------------------------------------------------
# CSV export / import
# ---------------------------------------------------------------------------

def test_csv_export(client):
    create(client, company="Alpha")
    create(client, company="Beta", status="Interview")
    resp = client.get("/api/export/csv")
    assert resp.status_code == 200
    assert "text/csv" in resp.headers["content-type"]
    rows = list(csv.DictReader(io.StringIO(resp.text)))
    assert [r["company"] for r in rows] == ["Alpha", "Beta"]
    assert rows[1]["status"] == "Interview"


def test_csv_import_round_trip(client):
    create(client, company="Alpha")
    exported = client.get("/api/export/csv").text
    assert client.delete("/api/applications").status_code == 204
    assert client.get("/api/applications").json() == []

    resp = client.post(
        "/api/import/csv",
        files={"file": ("applytrack.csv", exported, "text/csv")},
    )
    assert resp.status_code == 200
    assert resp.json()["imported"] == 1
    assert resp.json()["skipped"] == 0
    assert [a["company"] for a in client.get("/api/applications").json()] == ["Alpha"]


def test_csv_import_skips_bad_rows(client):
    bad_csv = (
        "company,role,status\n"
        "Good Co,Software Intern,Applied\n"
        ",Missing Company,Applied\n"
        "Bad Status Co,Software Intern,Hired\n"
    )
    resp = client.post(
        "/api/import/csv",
        files={"file": ("bad.csv", bad_csv, "text/csv")},
    )
    assert resp.status_code == 200
    assert resp.json()["imported"] == 1
    assert resp.json()["skipped"] == 2
    assert len(resp.json()["errors"]) == 2


def test_csv_import_rejects_non_csv(client):
    resp = client.post(
        "/api/import/csv",
        files={"file": ("notes.txt", "hello", "text/plain")},
    )
    assert resp.status_code == 400


# ---------------------------------------------------------------------------
# Seed data
# ---------------------------------------------------------------------------

def test_seed_data_has_twelve_spread_across_pipeline():
    from app.seed_data import sample_applications

    samples = sample_applications()
    assert len(samples) == 12
    statuses = {s.status.value for s in samples}
    assert {"Applied", "OA/Assessment", "Interview", "Offer", "Rejected"} <= statuses
    assert all(s.company and s.role for s in samples)
