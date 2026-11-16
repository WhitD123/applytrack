# ApplyTrack — Internship Application Tracker

A full-stack web app for tracking internship applications through the
whole pipeline — Applied → OA/Assessment → Interview → Offer/Rejected —
with a stats dashboard, deadline reminders, CSV import/export, and a
per-application outreach log (who you contacted, when, and how).

I built it because I was tracking ~190 internship applications in a
spreadsheet and kept losing deadlines, req IDs, and follow-ups. This
is the tool I actually wanted to use.

## Demo

Run it, then open **http://localhost:8000**. It starts with 12 sample
applications so the dashboard, filters, and deadlines have something
to show. Add your own, or click **Clear all data** to start fresh.

- **Stats cards** — total applications, response rate, interviews, offers, deadlines due in the next 7 days.
- **Pipeline chips** — one click filters the table to a single status.
- **Upcoming deadlines** — non-rejected applications due within 7 days, soonest first.
- **Table** — search by company/role, filter by status and term, sort by deadline / date applied / company. Each row links to the original posting and shows its req ID.
- **Add / Edit** — modal form for every field (company, role, location, term, req ID, date applied, status, deadline, pay, notes, link).
- **Outreach log** — per application, log alumni/recruiter contacts (name, date, channel: Email / LinkedIn / Phone / Other, notes). Deleting an application deletes its outreach log too.
- **CSV** — Export downloads all applications; Import re-uploads a CSV in the same format and reports how many rows imported vs. skipped (bad rows are skipped, not fatal).

## Stack

| Layer | Choice | Why |
|---|---|---|
| Backend | **FastAPI** (Python 3.12) | Type-checked request validation, auto-generated docs at `/docs` |
| Database | **SQLite via stdlib `sqlite3`** | No ORM — every query is a visible, parameterised SQL statement I can explain |
| Validation | **Pydantic** (bundled with FastAPI) | Missing company/role, bad status, bad date, bad link → 422 automatically |
| Frontend | **Vanilla HTML/CSS/JS**, no build step | Served by the backend itself; nothing to compile or bundle |
| Tests | **pytest + FastAPI TestClient** | Each test gets a fresh temp-database |

## Architecture

```
ApplyTrack/
├── app/
│   ├── main.py        # FastAPI app: all routes, serves the frontend
│   ├── database.py    # sqlite3 schema, connections, stats queries
│   ├── models.py      # Pydantic request/response models + validation
│   └── seed_data.py   # the 12 sample applications
├── static/
│   ├── index.html     # dashboard page
│   ├── styles.css
│   └── app.js         # fetch() calls to /api/*, renders table + stats
├── tests/
│   └── test_api.py    # 29 tests: CRUD, validation, filters, stats,
│                      #   outreach, CSV round-trip, seed data
├── seed_db.py         # CLI: seed / --force / --clear / --clear --no-seed
├── requirements.txt
├── run.sh             # first-run setup + start server
└── run_tests.sh       # run the test suite
```

Data flow: browser → `fetch("/api/...")` → FastAPI route → Pydantic
validation → parameterised `sqlite3` query → JSON back. The frontend
holds no state of its own; every change re-fetches from the API.

**Response rate** is defined as the share of applications that got any
response — i.e. moved out of `Applied` into OA/Assessment, Interview,
Offer, or Rejected. **Upcoming deadlines** are non-rejected
applications due within the next 7 days (today included).

## How to run

```bash
bash run.sh
# → http://localhost:8000
```

`run.sh` creates a virtual environment (`.venv`), installs
`requirements.txt`, seeds the sample data on a fresh database, and
starts Uvicorn with auto-reload. Manual equivalent:

```bash
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
.venv/bin/python seed_db.py        # optional: 12 sample applications
.venv/bin/uvicorn app.main:app --reload --port 8000
```

To start with an **empty** tracker instead of sample data:

```bash
.venv/bin/python seed_db.py --clear --no-seed
```

The database is a single file, `data/applytrack.db` (git-ignored).
Set `APPLYTRACK_DB=/path/to/file.db` to use a different location.

## API

Interactive docs: **http://localhost:8000/docs**

```bash
# Health
curl localhost:8000/api/health
# {"status":"ok"}

# List, filtered + sorted (deadline sort puts no-deadline rows last)
curl "localhost:8000/api/applications?status=Interview&sort=deadline"
curl "localhost:8000/api/applications?q=texas&term=Summer%202027"

# Create (201) — company + role are required, status must be one of
# Applied | OA/Assessment | Interview | Offer | Rejected
curl -X POST localhost:8000/api/applications \
  -H 'Content-Type: application/json' \
  -d '{"company":"Acme Corp","role":"Software Engineering Intern",
       "location":"Austin, TX","term":"Summer 2027","req_id":"REQ-1",
       "date_applied":"2026-11-10","status":"Applied",
       "deadline":"2026-12-01","pay":"$30/hr"}'

# Read / replace / delete one
curl localhost:8000/api/applications/1
curl -X PUT localhost:8000/api/applications/1 -H 'Content-Type: application/json' \
  -d '{"company":"Acme Corp","role":"Software Engineering Intern","status":"Interview"}'
curl -X DELETE localhost:8000/api/applications/1   # 204

# Stats dashboard
curl localhost:8000/api/stats
# {"total":12,"by_status":{"Applied":5,"OA/Assessment":2,"Interview":3,
#  "Offer":1,"Rejected":1},"response_rate":0.583,"responded":7,
#  "upcoming_deadlines":[...],"upcoming_count":5}

# Outreach log for one application
curl localhost:8000/api/applications/1/outreach
curl -X POST localhost:8000/api/applications/1/outreach \
  -H 'Content-Type: application/json' \
  -d '{"contact_name":"Jane Alum","channel":"LinkedIn","notes":"Asked for advice"}'
curl -X DELETE localhost:8000/api/outreach/1   # 204

# CSV export / import
curl -O localhost:8000/api/export/csv
curl -X POST localhost:8000/api/import/csv -F file=@applytrack.csv
# {"imported":12,"skipped":0,"errors":[]}
```

Error behaviour: unknown application id → `404`; invalid body
(missing company, bad status, bad date, non-http link) → `422`;
non-CSV upload → `400`.

## Tests

```bash
bash run_tests.sh
# or: .venv/bin/python -m pytest -v
```

29 tests, each against a fresh temporary SQLite database (via the
`APPLYTRACK_DB` env var — the real `data/applytrack.db` is never
touched). Coverage: CRUD + 404s, validation errors (missing company,
empty company, missing role, bad status/date/link), filtering by
status/term, search, deadline sort, stats math (counts, response
rate, 7-day window), outreach CRUD + cascade delete, CSV export,
CSV import round-trip, CSV import skipping bad rows, seed data shape.

## Design decisions

- **SQLite + raw SQL instead of an ORM.** For a single-user local
  tracker, an ORM adds a layer I would have to explain without adding
  anything; plain parameterised SQL is readable, testable, and fast
  enough at this scale.
- **Validation in Pydantic, not in route handlers.** One model defines
  the rules once; every route (and the CSV importer) reuses them, so
  a bad status is rejected identically everywhere.
- **No frontend framework.** The UI is a table, a form, and a few
  cards — vanilla JS + `fetch()` is the whole of it, with no build
  step to break. The backend serves the static files, so the app is
  one process: `uvicorn app.main:app`.
- **Dates relative to today in seed data.** Deadlines are computed
  from the current date when seeding, so the "upcoming deadlines"
  section always demonstrates correctly instead of going stale.
- **Sample data is clearly labelled.** The UI shows a banner while
  seeded rows are present, the README says the rows are illustrative,
  and one click clears them.

## What I would add next

- Email reminders for deadlines (background job + SMTP).
- A per-company response-time chart (days from Applied → first response).
- Authentication, so the tracker can be hosted instead of run locally.
