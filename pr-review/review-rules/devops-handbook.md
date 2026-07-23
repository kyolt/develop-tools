# devops-handbook-specific Review Rules

## Stack Context
- **Documentation repo** (handbook / runbooks / guides). Almost entirely Markdown, a little YAML, occasional helper script.
- Do **not** apply application-code rules here. Review as documentation: correctness, clarity, safety of documented commands.

## Documentation Review [should / nit]
- **Correctness of documented commands**: any shell/kubectl/terraform/gh command in a runbook must be accurate and safe. A wrong `kubectl delete` or unscoped command in a handbook is high-impact — flag as `must` if it could cause data loss or an outage when copy-pasted.
- **Destructive commands** without a warning, dry-run, or scope (namespace/context) → flag.
- **Secrets / credentials / internal hostnames** accidentally pasted into docs.
- Stale references: links, file paths, repo names, tool versions that no longer exist.
- Broken internal links / anchors; broken Markdown tables or code fences.
- Step ordering in procedures (a step that depends on a later step).

## Clarity [nit]
- Ambiguous instructions, undefined acronyms on first use, inconsistent terminology that hurts searchability.
- Typos in commands matter more than typos in prose — a typo'd command gets copy-pasted and fails.

## Keep It Light
- This repo rarely needs `must` findings. Prefer a few high-value clarifications over volume. Don't nitpick prose style.
