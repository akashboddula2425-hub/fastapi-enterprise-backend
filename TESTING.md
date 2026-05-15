# Testing Guide

End-to-end walkthrough for verifying every feature. Every payload below is **copy-paste ready** — paste into Swagger UI's "Try it out" → "Request body" boxes.

---

## Prerequisites

1. **Docker Desktop** installed and running (whale icon in system tray)
2. Stack started:
   ```bash
   docker-compose up --build
   ```
3. Wait until you see `Uvicorn running on http://0.0.0.0:8000`
4. Open **http://localhost:8000** in your browser (auto-redirects to Swagger UI)

---

## Step 1 — Health check (no auth needed)

**Endpoint:** `GET /api/health`

Just click "Try it out" → "Execute".

**Expected response (200):**
```json
{
  "status": "healthy",
  "db": "connected"
}
```

---

## Step 2 — Sign up

**Endpoint:** `POST /api/auth/signup`

**Request body:**
```json
{
  "email": "alice@example.com",
  "password": "validpass123",
  "full_name": "Alice Tester"
}
```

**Expected response (201):**
```json
{
  "id": "<uuid>",
  "email": "alice@example.com",
  "full_name": "Alice Tester",
  "is_active": true,
  "created_at": "...",
  "updated_at": "..."
}
```

### Negative test — duplicate email

Send the **same** request body again.

**Expected response (409):**
```json
{
  "error": {
    "code": 409,
    "message": "A user with this email already exists"
  }
}
```

### Negative test — invalid email

```json
{
  "email": "not-an-email",
  "password": "validpass123",
  "full_name": "Bad"
}
```

**Expected response (422):** validation error with field-level details.

### Negative test — short password

```json
{
  "email": "shortpw@example.com",
  "password": "abc",
  "full_name": "Bad"
}
```

**Expected response (422):** password must be at least 8 chars.

---

## Step 3 — Log in

**Endpoint:** `POST /api/auth/login`

⚠️ This is an OAuth2 form, **not JSON**. Use the form fields in Swagger:

- `username`: `alice@example.com`
- `password`: `validpass123`

(Leave `grant_type`, `scope`, `client_id`, `client_secret` blank.)

**Expected response (200):**
```json
{
  "access_token": "eyJhbGc...",
  "token_type": "bearer"
}
```

**Copy the `access_token` value** — you'll paste it next.

### Negative test — wrong password

Try `password: wrongpass`.

**Expected response (401):**
```json
{
  "error": {
    "code": 401,
    "message": "Invalid email or password"
  }
}
```

---

## Step 4 — Authorize Swagger

1. Click the green **🔓 Authorize** button at the top right of Swagger UI.
2. Paste the `access_token` value from Step 3 into the box (no `Bearer` prefix needed — Swagger adds it).
3. Click **Authorize** → **Close**.

Every protected endpoint is now unlocked.

---

## Step 5 — Create a project

**Endpoint:** `POST /api/projects`

**Request body:**
```json
{
  "name": "Q2 Roadmap",
  "description": "Quarterly planning project"
}
```

**Expected response (201):**
```json
{
  "id": "<project-uuid>",
  "name": "Q2 Roadmap",
  "description": "Quarterly planning project",
  "owner_id": "<your-user-uuid>",
  "created_at": "...",
  "updated_at": "..."
}
```

**Copy the `id` value** — you'll paste it as `project_id` next.

---

## Step 6 — Create tasks (different priorities and statuses)

**Endpoint:** `POST /api/tasks`

Replace `<PROJECT_ID>` in each body with the id from Step 5.

### Task A — high priority, pending

```json
{
  "title": "Ship analytics endpoint",
  "description": "Implement /api/analytics with productivity metrics",
  "status": "pending",
  "priority": "high",
  "project_id": "<PROJECT_ID>",
  "tags": ["backend", "analytics"]
}
```

### Task B — low priority, pending

```json
{
  "title": "Write API docs",
  "status": "pending",
  "priority": "low",
  "project_id": "<PROJECT_ID>",
  "tags": ["docs"]
}
```

### Task C — high priority, in progress

```json
{
  "title": "Refactor service layer",
  "status": "in_progress",
  "priority": "high",
  "project_id": "<PROJECT_ID>"
}
```

### Task D — with a due date (used later for overdue check)

```json
{
  "title": "Submit weekly report",
  "status": "pending",
  "priority": "medium",
  "due_date": "2026-01-01T09:00:00Z",
  "project_id": "<PROJECT_ID>"
}
```

Each should return **201** with the task object. **Copy Task A's `id`** for Step 9.

---

## Step 7 — List tasks (verify pagination, filtering, sorting)

**Endpoint:** `GET /api/tasks`

### 7a. List all your tasks

No params — should return all 4 tasks.

### 7b. Filter by status

URL param: `?status=pending`
Expected: **3 results** (Tasks A, B, D).

### 7c. Filter by priority

`?priority=high`
Expected: **2 results** (Tasks A, C).

### 7d. Combine filters

`?status=pending&priority=high`
Expected: **1 result** (Task A only).

### 7e. Sort by title ascending

`?sort_by=title&order=asc`
Expected: results ordered alphabetically by title.

### 7f. Sort by priority descending, limit 2

`?sort_by=priority&order=desc&limit=2&skip=0`
Expected: **2 results**, high-priority first.

### 7g. Filter by project

`?project_id=<PROJECT_ID>`
Expected: all 4 tasks.

---

## Step 8 — Update a task (PATCH)

**Endpoint:** `PATCH /api/tasks/{task_id}`

Use Task B's id in the path. Body:

```json
{
  "description": "Updated description",
  "priority": "high"
}
```

**Expected response (200):** task object with `priority: "high"` and updated `updated_at`.

---

## Step 9 — Complete a task (triggers ZenQuotes background job)

**Endpoint:** `PATCH /api/tasks/{task_id}` (use Task A's id)

**Request body:**
```json
{
  "status": "completed"
}
```

**Expected response (200):** task object with `status: "completed"`.

### Verify the quote was logged

The quote fetch happens in the **background** after the response is sent. Wait ~2 seconds, then in a separate terminal:

```bash
docker-compose exec db psql -U postgres -d app_db -c "SELECT action, target_entity, details->>'quote' AS quote, details->>'author' AS author FROM activities WHERE action='COMPLETED';"
```

**Expected output:**
```
  action   | target_entity |              quote               |    author
-----------+---------------+----------------------------------+----------
 COMPLETED | task          | <some motivational quote here>   | <author>
```

---

## Step 10 — Check audit log

```bash
docker-compose exec db psql -U postgres -d app_db -c "SELECT action, target_entity, created_at FROM activities ORDER BY created_at;"
```

**Expected:** rows showing CREATE/UPDATE/COMPLETED actions for each operation you performed. Every action is owner-scoped to your user.

---

## Step 11 — Analytics

**Endpoint:** `GET /api/analytics`

**Expected response (200):**
```json
{
  "total_tasks": 4,
  "completed_tasks": 1,
  "overdue_tasks": 1,
  "tasks_by_status": {
    "pending": 2,
    "in_progress": 1,
    "completed": 1
  },
  "active_projects_count": 1,
  "user_productivity": {
    "completion_rate": 0.25,
    "completed_last_7_days": 1,
    "average_completion_days": 0.0
  },
  "most_active_projects": [
    {
      "id": "<project-uuid>",
      "name": "Q2 Roadmap",
      "recent_task_activity": 4
    }
  ]
}
```

`overdue_tasks: 1` because Task D had a past due date and wasn't completed.

---

## Step 12 — Authorization tests (multi-user scoping)

This proves users can't access each other's data.

### 12a. Sign up a second user

Log out (Swagger Authorize → Logout), then sign up:

```json
{
  "email": "bob@example.com",
  "password": "validpass456",
  "full_name": "Bob Tester"
}
```

Log in as `bob@example.com`, authorize Swagger with Bob's token.

### 12b. Try to read Alice's project

`GET /api/projects/<ALICE_PROJECT_ID>`

**Expected response (403):**
```json
{
  "error": {
    "code": 403,
    "message": "You do not own this project"
  }
}
```

### 12c. Try to create a task in Alice's project

`POST /api/tasks`
```json
{
  "title": "Intruder task",
  "project_id": "<ALICE_PROJECT_ID>"
}
```

**Expected response (403).**

### 12d. Bob's analytics should be empty

`GET /api/analytics`

**Expected:** all counts = 0, `most_active_projects: []`. Confirms scoping.

---

## Step 13 — Error envelope consistency

Every error returns the same shape:

| Test | Expected status | Expected body |
|---|---|---|
| `GET /api/projects/00000000-0000-0000-0000-000000000000` | 404 | `{"error":{"code":404,"message":"Project not found"}}` |
| `GET /api/tasks/00000000-0000-0000-0000-000000000000` | 404 | `{"error":{"code":404,"message":"Task not found"}}` |
| `GET /api/nonexistent` | 404 | `{"error":{"code":404,"message":"Not Found"}}` |
| `GET /api/projects` without auth | 401 | `{"error":{"code":401,"message":"Not authenticated"}}` |
| `GET /api/projects` with `Authorization: Bearer fake` | 401 | `{"error":{"code":401,"message":"Could not validate credentials"}}` |

---

## Step 14 — Soft delete check

**Endpoint:** `DELETE /api/projects/{project_id}`

**Expected response (204)** — empty body.

Then:
- `GET /api/projects/{project_id}` → **404** (acts deleted)
- But in the DB:
  ```bash
  docker-compose exec db psql -U postgres -d app_db -c "SELECT id, name, is_deleted FROM projects;"
  ```
  The row is still there with `is_deleted = t`. ✅ Soft delete works.

---

## Step 15 — Run the test suite

```bash
docker-compose exec web pip install pytest==8.3.3 pytest-asyncio==0.24.0 aiosqlite==0.20.0
docker-compose exec web pytest -v
```

**Expected:**
```
============================ 31 passed in ~9s =============================
```

Coverage:
- 4 auth integration tests
- 4 task integration tests
- 12 failure-scenario tests (401/403/404/409/422/500 + quote fallback)
- 6 auth service unit tests (mocked repo)
- 5 quote client unit tests (mocked httpx)

---

## Step 16 — Observability check

Look at the `docker-compose up` output while you're making requests. Every request emits a structured JSON log line:

```json
{
  "timestamp": "2026-05-16T12:34:56.789Z",
  "level": "INFO",
  "logger": "app.request",
  "message": "request completed",
  "request_id": "abc123...",
  "method": "POST",
  "path": "/api/tasks",
  "status_code": 201,
  "duration_ms": 12.4
}
```

The `request_id` is also returned in the `X-Request-ID` response header so the client can correlate.

---

## Cleanup

When done testing:

```bash
docker-compose down -v
```

The `-v` flag wipes the Postgres data volume so the next `docker-compose up` starts clean.

---

## Quick smoke test (one-liner)

If you just want a 30-second sanity check that everything works, paste this into a terminal while the stack is running:

```bash
curl -s http://localhost:8000/api/health && echo && \
TOKEN=$(curl -s -X POST http://localhost:8000/api/auth/signup -H "Content-Type: application/json" -d '{"email":"smoke@test.com","password":"validpass123","full_name":"Smoke"}' > /dev/null && curl -s -X POST http://localhost:8000/api/auth/login -d "username=smoke@test.com&password=validpass123" | python -c "import sys,json;print(json.load(sys.stdin)['access_token'])") && \
echo "Token acquired" && \
curl -s http://localhost:8000/api/analytics -H "Authorization: Bearer $TOKEN"
```

**Expected:** health JSON, "Token acquired", and an analytics JSON with zero counts.
