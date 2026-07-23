# PR Review Output Format

## Standard Output Format

### PR Summary
- 2 to 5 bullets
- summarize what changed
- summarize likely impact areas

### Risk Summary
- `High`, `Medium`, or `Low`
- one short explanation

### Candidate Review Comments
Number each comment sequentially starting from 1. For each finding, use this exact structure:

**[N]**
- `type: <bug|logic|performance|naming|readability|typo|security|test|logging|deployment>`
- `severity: <must|should|nit>`
- `location: <file>:<line or range>` or `location: unknown`
- `comment: - <one concise review point>`
- `why: <one short impact-oriented reason>`
- `suggested_fix: <optional>`

---

## Example

### PR Summary
- Adds a new request validation path for batch updates.
- Updates the deployment chart to pass a renamed environment variable.
- Adjusts logging around retry failures.

### Risk Summary
Medium — The behavioral changes are limited, but there is some runtime risk around validation flow and deployment config drift.

### Candidate Review Comments

**[1]**
- `type: logic`
- `severity: must`
- `location: app/api/batch.py:84`
- `comment: - This early return bypasses validation when items is empty.`
- `why: Downstream code appears to assume validated input and may fail later with a less clear error.`
- `suggested_fix: Validate before the early-return path.`

**[2]**
- `type: deployment`
- `severity: must`
- `location: charts/api/templates/deployment.yaml:47`
- `comment: - The chart still injects APP_TOKEN, but the application now reads API_TOKEN; this looks like a rollout breakage risk.`
- `why: The pod may start without the required credential after deployment.`

**[3]**
- `type: logging`
- `severity: should`
- `location: worker/jobs.py:59`
- `comment: - The failure log here does not include the job identifier.`
- `why: This may make retries and downstream failures harder to trace during incidents.`

---

## Additional Formatting Rules
- Keep comments neutral and concise.
- Do not write essays.
- Do not add approval language.
- Do not add compliments unless explicitly requested.
- Do not include comments that are too weak to act on.
