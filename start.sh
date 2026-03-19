#!/bin/sh
set -e

echo "=== DATABASE_URL (masked) ==="
echo "$DATABASE_URL" | sed 's/:\/\/[^@]*@/:\/\/***@/'

echo "=== Running Alembic migrations ==="
alembic upgrade head
echo "=== Migrations done ==="

echo "=== Starting uvicorn ==="
exec uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000}
