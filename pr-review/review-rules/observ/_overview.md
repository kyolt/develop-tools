# observ Review Rules — Overview & Routing

Large Python monorepo. **Rules differ by which subfolder the PR touches** — apply the matching section(s) below:

| Changed path | Apply rules from |
|--------------|------------------|
| `backend/` | `backend.md` — API architecture, ORM, request handling |
| `streaming/` | `streaming.md` — streaming pipelines + GPU ops, performance & logic |
| other (`frontend_v2/`, `task-controller/`, `vlm-service/`, `iot_messaging/`, deployment) | general rules in `_base.md` + this overview |

If a PR spans multiple folders, apply each relevant section to the files in that folder. Do not apply backend ORM rules to streaming code or vice versa.

## Cross-cutting (all observ folders)
- Data-contract drift between backend response and frontend types.
- Typos in identifiers, log messages, and error bodies (they surface in production logs).
- The `_base.md` always-on mandate (performance / error handling / security) applies everywhere.
