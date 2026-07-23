# observ / backend — API Architecture Rules

Applies to PRs touching `backend/`. This is API-related architecture: request handling, persistence, business logic (Python — Django and/or FastAPI present).

## API Architecture & Correctness [must / should]
- **Endpoint/handler structure**: keep handlers thin — validation → service call → response. Flag business logic stuffed into route handlers.
- **ORM prefetch**: queries in loops → `select_related()` / `prefetch_related()` (Django) or `joinedload()` / `selectinload()` (SQLAlchemy). Flag N+1 like `order.user.name` in a loop.
- **Transaction boundaries**: multi-write operations wrapped in a transaction; rollback on error.
- **Status codes**: correct 4xx vs 5xx; not conflated under one catch.
- **Response/serializer shape changes**: backward-compatibility for clients; flag silent field renames/removals.
- **Migration ordering & reversibility** (Django migrations).
- **Permission / auth gaps** on new or changed endpoints.

## Async / Sync [must]
- No blocking I/O in `async def` (`requests`, sync DB drivers, `time.sleep`, blocking `open()`).
- Missing `await` on coroutines (silent no-op).

## Error Handling [must / should]
- No `except: pass` / bare `except Exception` swallowing; rollback on error path; `logger.exception(...)` (keep traceback); include request/entity context.

(Performance, error handling, security baseline from `_base.md` always apply.)
