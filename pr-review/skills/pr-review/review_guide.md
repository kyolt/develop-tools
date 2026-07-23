# PR Review Guide

## Goal
Produce high-signal draft PR review comments that a human can quickly filter before posting anything to GitHub.

Focus on:
- correctness
- logic
- performance
- naming
- readability
- typo / wording
- security
- test impact
- logging / observability
- deployment risk

Keep comments concise, neutral, and actionable.

---

## Review Dimensions

### 1. Correctness
Check whether the change can produce incorrect behavior.

Look for:
- wrong conditions
- broken branches
- missing validation
- incorrect assumptions
- bad return values
- inconsistent state changes
- incorrect error handling

### 2. Logic
Check whether the implementation matches likely intended behavior.

Look for:
- edge cases
- ordering issues
- invalid transitions
- partial updates
- async / concurrency mistakes
- retry / timeout mistakes
- incomplete rollback or recovery logic

### 3. Performance
Check for meaningful efficiency issues.

Look for:
- repeated DB / network / disk calls
- unnecessary recomputation
- inefficient ORM usage
- blocking operations in hot paths
- unbounded fan-out
- unnecessary serialization / parsing
- large avoidable allocations

Do not comment on micro-optimizations unless impact is likely meaningful.

### 4. Naming
Check whether names are precise and consistent.

Look for:
- misleading names
- generic names where precision matters
- inconsistent terminology
- names that hide scope, unit, or intent

### 5. Readability / Maintainability
Check whether future maintainers can understand and safely change the code.

Look for:
- overly complex branching
- duplicated logic
- hidden coupling
- magic constants without rationale
- broad functions doing too many things
- unclear control flow

### 6. Typo / Wording
Check text that users, operators, or developers may read.

Look for:
- spelling mistakes
- grammar mistakes
- misleading wording
- unclear logs
- inconsistent terminology
- unclear config descriptions or docs wording

### 7. Security / Safety
Check for obvious security or operational safety concerns.

Look for:
- missing auth / permission checks
- unsafe trust of external input
- injection risk
- unsafe deserialization
- secret leakage
- dangerous logs
- unsafe shell or script patterns
- insecure defaults

### 8. Test Impact
Check whether changed behavior is still well validated.

Look for:
- changed behavior without test updates
- missing regression tests
- missing edge-case coverage
- brittle tests
- tests that no longer match intended behavior

### 9. Logging / Observability
Check whether the change remains debuggable and observable.

Look for:
- missing failure logs
- missing identifiers in logs
- low-context logs
- noisy logs
- sensitive data in logs
- inconsistent wording hurting searchability

### 10. Deployment / Operational Risk
Check whether the change introduces rollout or runtime risk.

Look for:
- Helm values / template mismatch
- selector / label mismatch
- env var drift
- readiness / liveness breakage
- migration ordering issues
- rollback difficulty
- CI/CD trigger mistakes
- image tag / version drift
- non-backward-compatible config changes

---

## Comment Selection Rules
Only emit a comment if at least one is true:
- it may cause incorrect behavior
- it may cause confusing behavior
- it adds meaningful maintenance cost
- it creates real performance risk
- it weakens security or operational safety
- it reduces debugging visibility
- it introduces deployment or rollback risk
- it leaves important changed behavior insufficiently tested
- it introduces meaningful naming or wording confusion

Skip comments that are:
- purely cosmetic
- already enforced by tooling
- too speculative
- not actionable
- redundant with a stronger finding

---

## Severity Guidance

### must
Use when the issue is likely to cause:
- broken behavior
- data inconsistency
- security exposure
- major regression risk
- severe deployment problem
- clearly incorrect logic

### should
Use when the issue is important but not clearly blocking:
- meaningful maintainability issue
- meaningful performance risk
- missing validation with moderate risk
- missing logging in important failure paths
- missing tests for important changed behavior

### nit
Use when the issue is valid but minor:
- typo
- wording improvement
- naming precision
- small readability issue

---

## Comment Format
Each candidate comment must use:

- `type`: one of [bug, logic, performance, naming, readability, typo, security, test, logging, deployment]
- `severity`: one of [must, should, nit]
- `location`: `<file>:<line>` if available
- `comment`: one concise bullet-style review point
- `why`: one short sentence explaining impact
- `suggested_fix`: optional, only when reasonably clear

---

## Output Discipline
- Rank higher-signal findings first.
- Prefer one strong comment over several weak ones.
- Do not inflate comment count.
- If the PR appears low risk, say so.
- If evidence is incomplete, state uncertainty explicitly.
