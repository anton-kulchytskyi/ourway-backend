# OurWay Backend

FastAPI backend for OurWay — a family task manager with Kanban board and gamification.

## Tech Stack

- FastAPI (Python 3.12)
- PostgreSQL
- SQLAlchemy (async) + Alembic
- APScheduler (reminders)

## Local Development

```bash
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env
docker-compose up -d db
alembic upgrade head
uvicorn app.main:app --reload --port 8000
```

API runs at http://localhost:8000
Docs at http://localhost:8000/docs

## Deploy

Deployed on Railway. Every push to `main` triggers a new deployment.
