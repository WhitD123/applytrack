#!/usr/bin/env bash
# Start ApplyTrack: create the venv + install deps on first run,
# seed sample data on a fresh database, then serve on port 8000.
set -euo pipefail
cd "$(dirname "$0")"

if [ ! -d .venv ]; then
  echo "Creating virtual environment..."
  python3 -m venv .venv
fi
.venv/bin/pip install -q -r requirements.txt

if [ ! -f data/applytrack.db ]; then
  echo "Seeding sample data (run 'python seed_db.py --clear --no-seed' to start empty)..."
  .venv/bin/python seed_db.py
fi

echo "ApplyTrack running at http://localhost:8000  (Ctrl+C to stop)"
exec .venv/bin/uvicorn app.main:app --reload --port 8000
