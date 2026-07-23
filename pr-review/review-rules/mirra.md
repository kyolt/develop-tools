# mirra-specific Review Rules

## Stack Context
- Multi-component repo, but **review focus is the Python backend** (`backend/web/`, FastAPI). Other components (`frontend/`, `web-dt/`, `simulation/`, `carla/`, `omniverse/`) each have their own CLAUDE.md — keep those light and defer to component conventions.

## Python Backend [must / should — primary focus]
- **Basic logic correctness**: branching, edge cases, off-by-one, wrong conditionals. Verify the handler does what the PR says.
- **`Optional` not guarded**: e.g. `UploadFile.filename` is `Optional[str]`; calling `.endswith(...)` or interpolating it outside try/except → `AttributeError` → 500. Guard first. (Real bug found here.)
- **Async/sync discipline**: no blocking I/O in `async def`; missing `await`.
- **Batch / folder operations**: partial-failure handling and per-item error isolation (one bad item shouldn't 500 the whole batch); transaction boundaries.
- **Error handling**: no swallowed exceptions; rollback on error; `logger.exception(...)` with context.

## DB Schema & ORM [must / should — primary focus]
- **Schema changes**: new/changed columns — correct type, nullability, default, and index. Flag missing indexes on columns used in `WHERE` / `ORDER BY` / `JOIN`.
- **Migrations**: present for every model change, reversible, and ordered correctly relative to code that depends on them. Flag a model change with no migration (or vice versa).
- **Backward compatibility**: dropping/renaming a column or changing a type without a data-migration path → flag.
- **N+1 queries**: batch with `selectinload()` / `IN (...)`; flag ORM relationship access in loops.
- **Constraints & integrity**: unique/foreign-key constraints where the domain requires them; cascade behavior on delete is intentional.

## Naming / Contract Consistency [should / nit]
- Metadata-key vs schema/column-field mismatches (e.g. `config_meta_path` mapping to `scene_meta_path`) — align names or add a comment.
- Data-contract drift between backend response and frontend types.

## Other Components [nit — keep light]
- Frontend / simulation / 3D changes: only flag clear correctness or backend-contract issues. Be honest about uncertainty on runtime/simulation behavior you can't verify locally.

(Performance, error handling, security baseline from `_base.md` always apply.)
