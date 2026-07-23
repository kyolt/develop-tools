# observ-apiserver-specific Review Rules

## Stack Context
- Pure Python **FastAPI** HTTP server (poetry, `fastapi ^0.135`).
- API server for observ — request handling, persistence, event records.

## API Endpoint & Field Design [must / should — primary focus]
- **Field naming readability**: request/response field names should be clear and self-describing; flag abbreviations or names that hide units/meaning (`ts` vs `created_at`, `n` vs `count`).
- **Consistency across endpoints**: the same concept must use the same field name, type, and casing everywhere (e.g. don't mix `user_id` and `userId`, or `created_at` and `create_time` across endpoints). Flag drift from existing endpoints.
- **Response shape consistency**: error envelope, pagination shape, and timestamp format should match the established convention used by sibling endpoints.
- **Pydantic models**: prefer explicit typed fields over `dict`/`Any`; use enums for fixed value sets; mark optional vs required correctly.
- **Versioning / backward-compat**: flag silent field renames or removals that break existing clients.
- **Status codes**: correct 4xx vs 5xx; appropriate codes for not-found / validation / conflict.

## Basic API Performance [must / should]
- **N+1 queries** — batch with `WHERE id IN (...)` / `selectinload()`; flag DB calls inside loops.
- **Async/sync discipline** — no blocking I/O in handlers (`requests`, sync DB drivers, `time.sleep`, blocking `open()`); use async equivalents or `run_in_executor`.
- **Missing `await`** on coroutines.
- **Pagination/limits** on list endpoints — flag unbounded `SELECT *`.
- **DB session lifecycle** — `async with`; rollback on error path.

## Baseline (from _base.md)
Error handling and security always apply. Keep validation before use; correct status codes; never log secrets.

> Note: auth identity details (iss+sub) and base64-image specifics are **not** a focus for this repo — do not over-weight them.
