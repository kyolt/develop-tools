---
name: pr-review-select
description: Interactive comment selection after a PR review. Takes a numbered review output, asks the user which comments to keep, then either outputs the confirmed list or posts directly to GitHub. Use after /pr-review when the user wants to pick which comments to post.
---

# PR Review Select Skill

## Purpose
Present a numbered review result to the user, collect their selection, then either show the confirmed list or post directly to GitHub.

---

## Step 1: Determine input

The user may provide:
- A numbered review output (from a previous `/pr-review` run) — use it directly
- A PR reference only — run a standard review first, then proceed with the result

Accepted PR reference formats:
- PR number: `42`
- Full URL: `https://github.com/owner/repo/pull/42`
- owner/repo#number: `acme/api#42`

---

## Step 2: Display summary and ask for selection

Print a compact summary table of all comments:

```
#   severity  type        location
─────────────────────────────────────────────
1   must      logic       app/api/batch.py:84
2   must      deployment  charts/api/...:47
3   should    logging     worker/jobs.py:59
4   nit       naming      app/models/user.py:12
```

Then ask exactly:

> Which comments do you want to post? Enter numbers (e.g. `1 3 4`), `all`, or `none`.

Wait for the user's response before continuing.

---

## Step 3: Confirm selection

Reprint only the selected comments in full, then ask:

> Ready to post these N comment(s) to PR #<number>. Confirm? (yes / no)

If the user says **no** — ask if they want to adjust the selection and loop back to Step 2.
If the user says **yes** — proceed to Step 4.

---

## Step 4: Hand off to pr-review-post

Do **not** reimplement posting here. Once the user confirms in Step 3, invoke the
`pr-review-post` skill with the PR reference and the confirmed subset of
comments. That skill owns all posting logic — auth check, head SHA, payload,
`event: COMMENT`, unknown-location handling, natural comment voice, the top-level
must-fix summary, and cleanup.

This keeps a single source of truth for how comments are formatted and posted, so
the two paths (`pr-review-select` → post and direct `pr-review-post`) always
produce identical output.
