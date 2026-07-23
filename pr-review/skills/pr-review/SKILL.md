---
name: pr-review
description: Standard PR draft review. Use when the user shares a PR diff, URL, or code changes and asks for review feedback. Produces a structured draft with PR Summary, Risk Summary, and Candidate Review Comments for human review.
---

# PR Review Skill

Draft-review mode: this skill runs a multi-agent review, scores each finding for
confidence, filters out low-confidence noise, and returns a **draft** for the
human to confirm before anything is posted. It never approves and never
auto-posts.

## Before Starting

Read the following two files in this folder before beginning any review:

1. `review_guide.md` — review dimensions, severity guidance, and comment selection rules
2. `review_output_format.md` — required output structure and formatting rules

Then make a todo list from the steps below.

---

## Step 0: Resolve PR reference and fetch content

The PR argument can be in any of these formats:

| Format | Example | Resolution |
|--------|---------|------------|
| PR number | `42` | uses current repo directory |
| Full URL | `https://github.com/owner/repo/pull/42` | parsed directly |
| owner/repo#number | `acme/api#42` | split on `#`, use `-R` flag |

Fetch PR content before reviewing:

```bash
# PR number or URL
gh pr view <ref> --json title,body,baseRefName,headRefName,number,state,isDraft
gh pr diff <ref>

# owner/repo#number format
gh pr view 42 -R acme/api --json title,body,baseRefName,headRefName,number,state,isDraft
gh pr diff 42 -R acme/api
```

**Eligibility check.** Before doing any work, confirm the PR is worth reviewing.
Skip (and tell the user why) if it is closed/merged, a draft, an automated PR
(e.g. dependabot) that is obviously trivial, or already reviewed by you. Do not
burn agents on an ineligible PR.

Read the PR title and description first. Infer the intended behavior before
reviewing the diff.

---

## Step 1: Gather context

After fetching the diff:

- **Collect convention sources.** List the file *paths* (not contents) of the
  root `CLAUDE.md` (if any) plus any `CLAUDE.md` in directories the PR modifies.
  These are the authority for project-specific rules and are passed to the
  review and scoring agents.
- Use `Read` and `Grep` to understand surrounding context: read the full
  implementation of modified functions/classes, grep for callers of changed
  functions to gauge impact, and read related tests.
- Do not skip this — reviewing a diff without context misses logic bugs.

---

## Step 2: Parallel multi-agent review

Launch independent review agents **in parallel** (all in one message so they run
concurrently), each with a distinct lens. Scale the count to PR size — use 3 for
small PRs, up to 5 for larger ones. Each agent receives the diff, the list of
`CLAUDE.md` paths, and the relevant dimensions from `review_guide.md`, and
returns a list of findings. Every finding must include: `type`, `severity`,
`location`, `comment`, `why`, optional `suggested_fix`, **and the reason it was
flagged** (e.g. "CLAUDE.md adherence", "logic bug", "git history", "prior PR
comment", "code comment").

Suggested lenses (merge or drop to fit the PR):

- **Agent 1 — Convention / CLAUDE.md compliance.** Audit the change against the
  relevant `CLAUDE.md` files. Note that `CLAUDE.md` is guidance for *writing*
  code, so not every instruction applies at review time — only flag real,
  specific violations the `CLAUDE.md` actually calls out.
- **Agent 2 — Correctness & logic bug scan.** Read only the changed lines and do
  a focused scan for real bugs (dimensions 1–2 in `review_guide.md`). Favor
  large issues; ignore nitpicks and likely false positives.
- **Agent 3 — Historical context.** Read `git blame` / history of the modified
  code to spot bugs that only surface in light of how the code evolved.
- **Agent 4 — Prior review signal.** Look at previous PRs touching these files
  and any review comments on them that may also apply here.
- **Agent 5 — Operational dimensions.** Code comments compliance plus
  performance, security, test impact, logging, and deployment risk (dimensions
  3, 7–10).

Collect every finding, then **deduplicate** across agents (same location + same
underlying issue → keep the strongest single finding).

---

## Step 3: Confidence scoring & filtering

For each deduplicated finding, launch a parallel scoring agent that receives the
PR, the finding, and the `CLAUDE.md` paths, and returns a confidence score
**0–100**. For findings flagged due to a `CLAUDE.md` instruction, the scorer must
verify the `CLAUDE.md` actually calls out that issue specifically. Give the
scorer this rubric verbatim:

- **0** — Not confident at all. A false positive that doesn't survive light scrutiny, or a pre-existing issue.
- **25** — Somewhat confident. Might be real, might be a false positive; could not verify. If stylistic, not explicitly called out in the relevant CLAUDE.md.
- **50** — Moderately confident. Verified as a real issue, but may be a nitpick or rare in practice; relatively unimportant for this PR.
- **75** — Highly confident. Double-checked and very likely a real issue hit in practice; the PR's current approach is insufficient. Important, or directly named in the relevant CLAUDE.md.
- **100** — Absolutely certain. Double-checked and confirmed a real issue that happens frequently; evidence directly confirms it.

**Filter:** keep only findings scoring **≥ 80**. Note how many were filtered out
(e.g. "3 lower-confidence findings dropped") so the human knows the draft was
pruned — do not silently discard.

### False positives to filter (for Steps 2 and 3)

- Pre-existing issues on lines the PR did not modify
- Things that look like bugs but are not
- Pedantic nitpicks a senior engineer wouldn't raise
- Anything a linter / typechecker / compiler would catch (imports, type errors, formatting) — assume CI runs these; do not build or typecheck yourself
- General quality gaps (test coverage, docs) unless a relevant `CLAUDE.md` requires them
- Issues named in `CLAUDE.md` but explicitly silenced in code (e.g. lint-ignore)
- Functional changes that are likely intentional and part of the broader change

---

## Step 4: Compose the draft

Follow all rules in `review_guide.md` and produce output exactly as specified in
`review_output_format.md`. Additional requirements:

- **Primary focus: logic and correctness.** Style/formatting/cosmetic issues are
  low priority unless they cause confusion.
- Rank surviving findings by importance; prefer one strong comment over several
  weak ones. Keep comments concise and bullet-style.
- Do not approve the PR. Treat all output as draft comments for human review.
- Be explicit when something is uncertain.

Return exactly:

1. PR Summary
2. Risk Summary
3. Candidate Review Comments (only findings that passed the ≥ 80 filter)
4. Summary verdict — one sentence: overall risk level, whether you'd block or
   approve, and why. Include the count of lower-confidence findings that were
   filtered out.

If no finding passes the filter, still return the PR Summary, Risk Summary, and
verdict, and state plainly that no high-confidence issues were found.

---

## Step 5: Post after human confirmation

Once the human confirms which comments to post, use the `pr-review-post` skill to
post them as inline comments via `gh api`. Never post before the human confirms.
