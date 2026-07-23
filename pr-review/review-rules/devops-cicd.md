# devops-cicd-specific Review Rules

## Stack Context
- **NOT a Python service.** This is the central CI/CD repo: GitHub Actions workflows (`.github/workflows/`) + reusable **composite actions** (`common-actions/`: deploy, docker-build, github-release, helm-push, set-image-tag, set-github-runner) that are synced out to other repos (e.g. visionai-deploy).
- Mostly YAML + shell. Review through a pipeline-safety lens, not an application lens.

## GitHub Actions / Workflows [must / should]
- **Trigger conditions**: `on:` push/pull_request branch & path filters intentional? An over-broad trigger can deploy on the wrong branch. A too-narrow one silently skips.
- **Secrets**: every `${{ secrets.X }}` referenced must exist; never echo secrets; mask sensitive outputs. No secrets in plaintext or committed env files.
- **Permissions**: `permissions:` scoped to least privilege (esp. `contents`, `packages`, `id-token` for OIDC).
- **Pinning**: third-party actions pinned to a SHA or trusted tag, not a moving `@main`.
- **Concurrency**: deploy/release workflows should set `concurrency:` to avoid overlapping runs racing on the same environment.
- `timeout-minutes` on long-running jobs.

## Composite Actions (common-actions/) [must]
- These are consumed by **many repos** — a breaking change to inputs/outputs ripples everywhere. Flag removed/renamed inputs, changed defaults, or changed output names as high-impact backward-compat risks.
- **Shell safety** in `run:` steps: quote variable expansions (`"$VAR"`), `set -euo pipefail` where appropriate, no unquoted `$()` that word-splits.
- **Image tag / digest correctness**: the tag produced by `set-image-tag` / `docker-build` must match what `deploy` / `helm-push` consumes. Tag/digest drift = deploying the wrong image.
- ECR `cache-from` / `cache-to` settings correct and consistent.

## Deploy / Release Safety [must / should]
- Rollback path: is there a way back if a deploy fails? Flag irreversible steps.
- Migration ordering relative to deploy.
- The sync-to-visionai-deploy workflow: verify it doesn't drift or overwrite downstream customizations unexpectedly.

## Shell Scripts (scripts/, action steps) [should]
- Quoting, `pipefail`, error propagation (a failing step in a `&&` chain must fail the job).
- Dead guards (a check on a variable that always has a non-empty default).
