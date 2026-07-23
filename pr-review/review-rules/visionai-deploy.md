# visionai-deploy-specific Review Rules

## Stack Context
- **Deployment / infra repo**, almost entirely YAML + config. Contains: `helm/` charts, `ansible/`, `terraform/`, `deployment/`, `runner/` (github-runner values), `auto-vpa/` (VPA chart), `common-actions/` (synced from devops-cicd), `config/`, `envrc-files/`.
- Review through an infra-safety / blast-radius lens. Almost no application code.

## Helm Charts [must / should]
- **Chart value ↔ template mismatch**: a value referenced in a template (`.Values.x.y`) that doesn't exist in `values.yaml`, or vice versa.
- **Resource requests/limits** set on every workload; VPA (`auto-vpa`) interactions sane.
- Readiness / liveness probes present and correct.
- Image tag/digest: immutable references; the tag deployed matches what CI built.
- Secrets via secret refs, never inlined in values.

## Kubernetes Manifests [must]
- **Selector / label mismatch** between Service and Deployment/Pod → traffic silently goes nowhere. High-recurrence infra bug.
- Namespace correctness; RBAC scoped to least privilege.
- `hostNetwork` / `privileged` / host mounts only with justification.
- env-var drift between environments (`config/`, `envrc-files/`).

## Terraform [must / should]
- Hardcoded credentials / secrets (must never be committed).
- Resource naming consistency; missing variable descriptions/defaults.
- State-affecting changes: anything that forces resource **replacement** (destroy+create) of stateful infra — call it out loudly.
- Provider/module version pinning.

## Ansible [should]
- Idempotency (a task that isn't idempotent and re-runs destructively).
- `no_log: true` on tasks handling secrets.
- Hardcoded hosts/IPs that should be inventory variables.

## Cross-cutting [must]
- **Blast radius**: this repo deploys real environments. For any change, ask: what breaks if this is wrong, and is it reversible? Flag unsafe defaults and irreversible operations.
- Env-var / config drift across environments.
- Be honest when a change's runtime effect can't be verified from the manifest alone.
