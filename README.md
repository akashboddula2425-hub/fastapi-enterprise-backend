# FastAPI Enterprise Backend

A production-style backend service: layered architecture, strict DTOs, JWT auth, audit logging, analytics, background jobs, and external API integration.

## Tech Stack

- Python 3.11+ / FastAPI
- PostgreSQL 15 + SQLAlchemy 2.0 (async / asyncpg)
- Alembic migrations
- JWT auth (python-jose) + bcrypt password hashing
- Docker + Docker Compose
- pytest + pytest-asyncio + httpx for tests

## Architecture

```
Client → Router → DTO Validation → Service Layer → Repository Layer → DB
```

Routes never touch the DB directly. Services hold business rules. Repositories own SQL.

```
app/
├── api/
│   ├── deps.py             # get_db, get_current_user, CurrentUser/DbSession aliases
│   ├── middleware.py       # request-id + JSON-log middleware
│   └── routes/             # auth, projects, tasks, analytics, health
├── core/
│   ├── config.py           # Pydantic Settings (env-driven)
│   ├── database.py         # async engine + sessionmaker
│   ├── exceptions.py       # AppException hierarchy
│   ├── logging.py          # JSON formatter + request_id ContextVar
│   └── security.py         # JWT + bcrypt helpers
├── dto/                    # Pydantic V2: Create/Update/Read/Filter DTOs
├── models/                 # SQLAlchemy 2.0 declarative models
├── repositories/           # BaseRepository[T] + per-entity repos
├── services/               # business logic (auth, project, task, analytics, activity)
└── integrations/           # external API clients (quote_client.py)
```

## Running with Docker (recommended)

```bash
git clone https://github.com/akashboddula2425-hub/fastapi-enterprise-backend.git
cd fastapi-enterprise-backend
cp .env.example .env
docker-compose up --build
```

> **Windows note:** `cp` works in PowerShell (it's aliased to `Copy-Item`). In `cmd.exe` use `copy .env.example .env` instead.

What this does:
1. Builds the `web` image (Python 3.11-slim, multi-stage).
2. Starts Postgres 15 with a healthcheck.
3. The `web` container waits for `db` to be healthy, then `entrypoint.sh` runs `alembic upgrade head` and launches uvicorn.

API is available at `http://localhost:8000` (which redirects to Swagger UI).

- Swagger UI: `http://localhost:8000/docs`
- ReDoc: `http://localhost:8000/redoc`
- OpenAPI JSON: `http://localhost:8000/openapi.json`

**End-to-end verification flow:** see [TESTING.md](TESTING.md) — copy-paste payloads that walk through every feature (auth, projects, tasks, filters/sort, background quote job, analytics, multi-user authorization, soft delete) in ~10 minutes.

## Running Locally (without Docker)

Requires **Python 3.11** (pinned dependencies — notably `psycopg2-binary==2.9.9` — don't have wheels for 3.13+).

```bash
python3.11 -m venv .venv
source .venv/bin/activate         # Windows: .venv\Scripts\activate
pip install -r requirements-dev.txt

cp .env.example .env
# Ensure POSTGRES_HOST=localhost in .env when running outside Docker

alembic upgrade head
uvicorn app.main:app --reload
```

## Endpoints

All routes (except `/api/health` and `/api/auth/*`) require `Authorization: Bearer <token>`.

| Method | Path | Notes |
| --- | --- | --- |
| GET | `/api/health` | DB-ping health probe |
| POST | `/api/auth/signup` | Register a user |
| POST | `/api/auth/login` | OAuth2-form, returns JWT |
| GET/POST | `/api/projects` | List/create (supports `sort_by`, `order`, `skip`, `limit`) |
| GET/PATCH/DELETE | `/api/projects/{id}` | Owner-scoped |
| GET/POST | `/api/tasks` | List supports filter DTO: `status`, `priority`, `assigned_user_id`, `project_id`, `sort_by`, `order`, `skip`, `limit` |
| GET/PATCH/DELETE | `/api/tasks/{id}` | Owner or assignee |
| GET | `/api/analytics` | Overview: totals, by-status, overdue, productivity, most-active projects |

### Filter examples

```
GET /api/tasks?status=pending&priority=high&sort_by=due_date&order=asc&limit=50
GET /api/projects?sort_by=name&order=asc
```

### Task completion side-effect

When a task transitions to `status=completed`, a background task fetches a random motivational quote from [ZenQuotes](https://zenquotes.io) and writes it to the `activities` table with `action="COMPLETED"`. The HTTP response is not blocked by the external call, and the integration falls back to a hardcoded quote on any network failure.

## Running Tests

**Recommended — inside the running container** (no Python version pain):

```bash
docker-compose up -d --build
docker-compose exec web pip install pytest==8.3.3 pytest-asyncio==0.24.0 aiosqlite==0.20.0
docker-compose exec web pytest -v
```

Expected output:
```
============================ 31 passed in ~9s =============================
```

**Or locally** (requires Python 3.11):

```bash
python3.11 -m venv .venv
source .venv/bin/activate
pip install -r requirements-dev.txt
pytest -v
```

Tests run against an in-memory SQLite database (aiosqlite) — no Postgres needed. The test client overrides `get_db` and patches `AsyncSessionLocal` so background tasks also write to the test DB.

Test layout:
- `tests/test_auth.py`, `tests/test_tasks.py` — API integration tests
- `tests/test_failure_scenarios.py` — 401/403/404/409/422/500 envelopes + quote-API fallback
- `tests/unit/` — isolated unit tests (mocked repos, mocked httpx)

## Configuration

All settings come from `.env` via Pydantic Settings. See [.env.example](.env.example) for the full list. The most important:

| Variable | Purpose |
| --- | --- |
| `SECRET_KEY` | JWT signing key — **change for production** |
| `POSTGRES_*` | Database connection (host=`db` inside Docker, `localhost` outside) |
| `ALLOWED_ORIGINS_RAW` | Comma-separated CORS origins (also accepts JSON-list form) |
| `ACCESS_TOKEN_EXPIRE_MINUTES` | JWT lifetime |
| `DEBUG` | Toggles SQL echo and DEBUG-level logs |

## Migrations

```bash
# Apply migrations (also run automatically by the container entrypoint)
alembic upgrade head

# Create a new revision after changing models
alembic revision --autogenerate -m "describe change"
```

The initial schema lives at `alembic/versions/0001_initial_schema.py`.

## Observability

Every request gets a `X-Request-ID` header (incoming value is preserved, otherwise generated). The request ID is bound to a `ContextVar` and emitted on every log line as part of the JSON envelope:

```json
{"timestamp": "...", "level": "INFO", "logger": "app.request", "message": "request completed",
 "request_id": "...", "method": "GET", "path": "/api/tasks", "status_code": 200, "duration_ms": 12.4}
```

DB errors are logged with full traceback server-side and returned to clients as a generic 500 envelope — no internals leak.

## Error envelope

All errors share the same response shape:

```json
{ "error": { "code": 404, "message": "Project not found" } }
```

Validation errors (422) additionally include a `details` array with per-field errors from Pydantic.

## Submission Artefacts

- Source: this repository
- `.env.example` — template environment file
- `Dockerfile` (multi-stage) + `docker-compose.yml`
- Alembic migration: `alembic/versions/0001_initial_schema.py`
- Tests: `tests/`
- API docs: auto-generated Swagger at `/docs` (use as the live API collection)
- [TESTING.md](TESTING.md) — step-by-step verification flow with copy-paste payloads
