# observ-event-logic-specific Review Rules

## Stack Context
- Pure Python logic package. Expression DSL (`expressions/`), custom triggers (`custom_trigger/`), geometry utils (`utils/`), inferences.
- No HTTP server / DB — this is correctness-critical pure logic. Weight findings toward logic correctness, registration completeness, and test coverage.

## Logic Correctness [must]
Flag any executor that does not implement what its model name says:
- `$overlap_all` / `$non_overlap_all`: must check against **all** sub-target classes, not just one.
- `$overlap_some` / `$non_overlap_some`: must check against **at least one**.
- `$with_all` / `$without_all`: all listed targets simultaneously present / absent.
- A `True` result must carry a **non-empty** match `set[str]` (except `$not`, `$vf_without`, `$without` which have no meaningful IDs). `(True, set())` or `(False, non_empty_set)` is a bug.
- Short-circuiting too early (returning on first match when all must match).
- Using `all_main_uids` where only matched ones should be returned, or vice versa.

## Custom Trigger Correctness [must]
- **`context.zones[ZONE_ID]` / dict access by key** → raises `KeyError` if absent. Use `.get()` + warn + graceful return (e.g. `return False, set(), [], extra_params`). This is the single most recurring bug in this repo.
- `bbox is None` not checked before `.crop()` / `.bounds` → `AttributeError`.
- Triggers that should return `warning_extras` / `extra_params` but don't — verify the full return tuple is consistent with siblings.
- Redundant reassignment of a loop variable to the same value (`item = extra_params.items[track_id]` when `item` is already the loop var) — misleading, flag it.

## Registration Completeness [must]
Every new `ExpXxxModel` must be registered in all of:
1. `ExpExpectBool` / `ExpExpectFloat` union in `models.py`
2. `bool_operator_executors` / `float_operator_executors` dict in `eval.py`
3. `model_rebuild()` in `models.py` if self-referential

Missing any one → silent parse failure or runtime `KeyError`.

## `_translation` Correctness [must]
Models delegating via `_translation` must produce a logically equivalent tree:
- `$without` = `$not($with(...))`
- `$without_some` = `$not($with_all(...))`
- `$without_all` = `$all([$without(t) for t in targets])`
- `$with_all` = `$all([$with(t) for t in targets])`, `$with_some` = `$any([$with(t) ...])`

Wrong translations are hard to spot because the executor delegates.

## Geometry Correctness [must]
- Image coordinates: **`y` increases downward** — `y=0` is top, `y=1` is bottom. A polygon over `y=0.5→1.0` is the **bottom** half. Misnaming `UPPER_HALF`/`LOWER_HALF` is a real recurring error here.
- Crop ratios producing zero-area / inverted boxes (`x1>=x2` or `y1>=y2`).
- `intersects()` vs `contains()` confusion; coordinates outside `[0,1]` not clamped.

## Test Coverage for New Logic [must]
Every new operator/trigger needs: base case (assert both `result` **and** match IDs), negative case `(False, set())`, empty input, and operator-specific edge (`_all`: partial targets → False; `_some`: one target → True; dwell/ratio: ratio-not-met, `has_enough_data=False`, `track_id < 0` skipped). Flag tests that assert only the bool and ignore the `set[str]` — match IDs are part of the contract.

## Symmetry & Duplication [should]
- New operator added without its symmetric counterpart, or `_some`/`_all` variants using different internal helpers.
- Copy-pasted "iterate main → iterate sub → check intersects → collect" loops; repeated `ObjectPairing` / `context.query_inference(...).crop(...)` boilerplate → point to `_pair_targets` as the existing abstraction.

## Typos & Naming [should / nit]
- DSL alias typos (`"$ovelap_all"`) break parsing **silently** — treat as `must` despite being a typo.
- Model class, executor function, and executor-map key must use the same operator name end to end.

## Package Upgrades & Dependencies [must / should]
- This is a **library/package** consumed by other repos — dependency bumps ripple downstream. For any `pyproject.toml` / `poetry.lock` change:
  - Flag **major-version** bumps (semver breaking) of pydantic, shapely/geometry libs, or other core deps — verify the code adapts to the new API.
  - Pydantic version changes are high-risk here (the DSL relies heavily on models / `model_rebuild()` / unions). Flag v1→v2 style migrations (`validator`→`field_validator`, `Config`→`model_config`, `.dict()`→`.model_dump()`).
  - Widening a version constraint (`^x` → `>=x`) that could pull an untested major — call it out.
  - Lockfile changed without the corresponding `pyproject.toml` constraint change (or vice versa) → inconsistent state.

## Backward Compatibility [must]
- This package has external consumers. Treat the **public API and the DSL grammar as a contract**:
  - Renaming/removing an existing operator alias, executor, or model field is a **breaking change** — flag unless the PR documents a deprecation path.
  - Changing the return tuple shape (`(bool, set[str], ...)`) of a trigger/executor → breaks callers.
  - Changing the semantics of an existing operator (vs adding a new one) → flag and require explicit intent.

## Documentation [should]
- New operators / triggers must be documented: docstring describing semantics, the DSL alias, and an example expression.
- Public API changes reflected in README / docs / changelog.
- Docstrings must match the implementation — flag stale docstrings that describe old behavior after a logic change.
