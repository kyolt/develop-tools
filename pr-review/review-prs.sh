#!/bin/bash
# Usage: review-prs.sh <repo|org/repo> <PR_NUMBER>[,PR_NUMBER...] [<repo> <PR_NUMBER>[,...] ...]
# Org defaults to linkervision, so you can just pass the repo name.
#
# Single repo:
#   review-prs.sh observ 101 102 103
#   review-prs.sh observ 101,102,103
#
# Multiple repos in one call (repo name / PR-list tokens alternate; a
# comma-separated list of numbers belongs to the repo named right before it):
#   review-prs.sh observ 12215,12221 mirra 549 vlm-inference-server 296
#
# Override the default org with: DEFAULT_ORG=other ~/.claude/review-prs.sh ...
# Or pass a full org/repo to use a different org for one group.
#
# Preview without posting (drafts only, nothing auto-posted) with:
#   DRY_RUN=1 review-prs ...

set -e

DEFAULT_ORG="${DEFAULT_ORG:-linkervision}"
RULES_DIR="$HOME/.claude/review-rules"
WORK_BASE="/tmp/claude-reviews"
# Base dir where each subfolder is an independent github repo.
# Override with: CODES_DIR=/path ~/.claude/review-prs.sh ...
CODES_DIR="${CODES_DIR:-$HOME/linker/codes}"
# Model for draft generation (`claude --print`). Empty = claude CLI default.
# Override with: REVIEW_MODEL=opus review-prs ...
REVIEW_MODEL="${REVIEW_MODEL:-}"
# Model for codex's adversarial verification pass. Empty = codex CLI default.
# Override with: CODEX_MODEL=gpt-5.1-codex-max review-prs ...
CODEX_MODEL="${CODEX_MODEL:-}"
mkdir -p "$WORK_BASE"

if [[ $# -lt 2 ]]; then
  echo "Usage: review-prs.sh <repo> <PR[,PR...]> [<repo> <PR[,PR...]> ...]"
  echo "Example: review-prs.sh observ 12215,12221 mirra 549   (org defaults to $DEFAULT_ORG)"
  exit 1
fi

if command -v codex &>/dev/null; then
  echo "🤖 codex available — findings will be adversarially verified, confidence ≥80 auto-posts."
else
  echo "⚠️  codex not found — falling back to Claude self-review only. Nothing will be auto-posted"
  echo "    (an independent verifier is required for that); everything goes to /pr-review-drafts."
fi

# Fail fast if a required tool is missing — otherwise it only surfaces deep
# inside a backgrounded job where the error is easy to lose.
for _tool in claude gh python3 git; do
  if ! command -v "$_tool" &>/dev/null; then
    echo "❌ Required tool '$_tool' not found in PATH. Install it before running."
    exit 1
  fi
done

# --- Parse args into (repo, pr-list) groups -------------------------------
# A token that is purely digits/commas is a PR number (or comma-list) for the
# most recently named repo. Any other token starts a new repo group. This
# supports both space-separated PRs for one repo (observ 101 102 103) and
# multiple repos in one call (observ 12215,12221 mirra 549).
REPOS=()
PR_LISTS=()
active_idx=-1
for tok in "$@"; do
  if [[ "$tok" =~ ^[0-9]+(,[0-9]+)*$ ]]; then
    if [[ $active_idx -lt 0 ]]; then
      echo "❌ PR number '$tok' given before any repo name."
      exit 1
    fi
    if [[ -z "${PR_LISTS[$active_idx]}" ]]; then
      PR_LISTS[$active_idx]="$tok"
    else
      PR_LISTS[$active_idx]="${PR_LISTS[$active_idx]},$tok"
    fi
  else
    REPOS+=("$tok")
    PR_LISTS+=("")
    active_idx=$((${#REPOS[@]} - 1))
  fi
done
for i in "${!REPOS[@]}"; do
  if [[ -z "${PR_LISTS[$i]}" ]]; then
    echo "❌ Repo '${REPOS[$i]}' was given no PR numbers."
    exit 1
  fi
done

# --- Reviews one repo's PRs (runs its own PRs in parallel) -----------------
review_repo() {
  local REPO="$1" PR_CSV="$2"
  if [[ "$REPO" != */* ]]; then
    REPO="$DEFAULT_ORG/$REPO"
  fi
  local REPO_NAME; REPO_NAME=$(basename "$REPO")

  # De-duplicate PR numbers, preserving order. The same repo+PR listed twice
  # would otherwise spawn two jobs sharing one worktree dir / head ref and race.
  local -a _raw_prs; IFS=',' read -ra _raw_prs <<< "$PR_CSV"
  local -a PR_NUMBERS=(); local _p
  for _p in "${_raw_prs[@]}"; do
    [[ " ${PR_NUMBERS[*]} " == *" $_p "* ]] || PR_NUMBERS+=("$_p")
  done

  # Build prompt: base + repo-specific rules.
  # A repo's rules can be EITHER a single file (<repo>.md) OR a directory
  # (<repo>/*.md, for repos whose rules differ by subfolder). Directory wins.
  local PROMPT; PROMPT=$(cat "$RULES_DIR/_base.md")
  local loaded="_base.md"
  if [[ -d "$RULES_DIR/$REPO_NAME" ]]; then
    for f in "$RULES_DIR/$REPO_NAME"/*.md; do
      [[ -e "$f" ]] || continue
      PROMPT="$PROMPT"$'\n\n'"$(cat "$f")"
      loaded="$loaded + $REPO_NAME/$(basename "$f")"
    done
  elif [[ -f "$RULES_DIR/$REPO_NAME.md" ]]; then
    PROMPT="$PROMPT"$'\n\n'"$(cat "$RULES_DIR/$REPO_NAME.md")"
    loaded="$loaded + $REPO_NAME.md"
  else
    loaded="$loaded (no $REPO_NAME rules found)"
  fi
  echo "📋 [$REPO_NAME] Loaded rules: $loaded"

  local LOCAL_REPO="$CODES_DIR/$REPO_NAME"
  if [[ ! -d "$LOCAL_REPO/.git" ]]; then
    echo "❌ [$REPO_NAME] Repo not found at $LOCAL_REPO (set CODES_DIR or clone it there first)"
    return 1
  fi
  echo "🔄 [$REPO_NAME] Fetching latest $REPO..."
  git -C "$LOCAL_REPO" fetch --all --prune -q

  # Appended (automation-only) so the confidence pipeline can parse findings
  # programmatically. _base.md's human-facing format is untouched — this is
  # additive, for review-prs.sh's headless pipeline specifically.
  # (Template lives in its own file — apostrophes/backticks inside a heredoc
  # nested in $(...) confuse bash's lexer, so keep this text out of the script.)
  local FINDINGS_ADDENDUM
  FINDINGS_ADDENDUM=$(cat "$HOME/.claude/scripts/findings-addendum.template.md")
  local BT='`'
  FINDINGS_ADDENDUM="${FINDINGS_ADDENDUM//===JSON_FENCE_OPEN===/${BT}${BT}${BT}json}"
  FINDINGS_ADDENDUM="${FINDINGS_ADDENDUM//===JSON_FENCE_CLOSE===/${BT}${BT}${BT}}"

  local pr_pids=()
  local -a WORK_DIRS=() PR_REFS=()
  for PR_NUMBER in "${PR_NUMBERS[@]}"; do
    local WORK_DIR="$WORK_BASE/$REPO_NAME-pr-$PR_NUMBER"
    local RAW_FILE="$WORK_BASE/$REPO_NAME-pr-$PR_NUMBER.raw.md"
    local OUT_FILE="$WORK_BASE/$REPO_NAME-pr-$PR_NUMBER.review.md"
    local BRANCH; BRANCH=$(gh pr view "$PR_NUMBER" --repo "$REPO" --json headRefName -q .headRefName)

    echo "▶ [$REPO_NAME#$PR_NUMBER] ($BRANCH) → draft will be saved to $OUT_FILE"

    # Use the PR's own head ref (GitHub always keeps refs/pull/<N>/head, even
    # after the source branch is deleted post-merge) rather than
    # origin/<branch>, which breaks for merged/closed PRs.
    local PR_REF="pr-$PR_NUMBER-head"
    git -C "$LOCAL_REPO" fetch origin "pull/$PR_NUMBER/head:$PR_REF" -f -q
    git -C "$LOCAL_REPO" worktree remove --force "$WORK_DIR" 2>/dev/null || true
    rm -rf "$WORK_DIR"
    git -C "$LOCAL_REPO" worktree add "$WORK_DIR" "$PR_REF" -q
    # Defer cleanup until after all PRs finish (see the sequential pass below).
    # `git worktree remove` / `branch -D` mutate the shared local repo, so
    # running them inside the background subshell would race with the next PR's
    # `worktree add` and with other subshells' cleanup on the same repo.
    WORK_DIRS+=("$WORK_DIR")
    PR_REFS+=("$PR_REF")

    (
      cd "$WORK_DIR"
      # Repo's own REVIEW.md (if any), from the PR's checked-out tree. Same file
      # the managed Code Review feature reads; injected here as highest-priority
      # rules so one REVIEW.md serves both. Falls back to nothing when absent.
      local REVIEW_MD=""
      [[ -f "$WORK_DIR/REVIEW.md" ]] && REVIEW_MD=$'\n\n# Repo REVIEW.md (highest priority)\n\n'"$(cat "$WORK_DIR/REVIEW.md")"

      # 1. Headless draft generation (Claude). Raw output isn't interactive —
      #    it's post-processed below, then this temp file is discarded. stderr
      #    goes to a separate file so CLI chatter can't corrupt the findings
      #    the confidence pipeline parses out of $RAW_FILE.
      printf "%s%s\n%s\n\nReview PR #%s in repo %s. Fetch the PR diff with: gh pr diff %s --repo %s" \
        "$PROMPT" "$REVIEW_MD" "$FINDINGS_ADDENDUM" "$PR_NUMBER" "$REPO" "$PR_NUMBER" "$REPO" \
        | claude --print --dangerously-skip-permissions ${REVIEW_MODEL:+--model "$REVIEW_MODEL"} > "$RAW_FILE" 2>"$RAW_FILE.err"

      # 2. Confidence pipeline: adversarial verification (codex, or a
      #    conservative Claude fallback) + auto-post findings >= threshold.
      #    Runs while the worktree still exists so the verifier can read the
      #    actual checked-out code.
      python3 "$HOME/.claude/scripts/pr_confidence_review.py" \
        --repo "$REPO" --pr "$PR_NUMBER" --branch "$BRANCH" \
        --raw "$RAW_FILE" --out "$OUT_FILE" --cwd "$WORK_DIR" \
        ${DRY_RUN:+--dry-run} \
        ${CODEX_MODEL:+--codex-model "$CODEX_MODEL"}

      rm -f "$RAW_FILE" "$RAW_FILE.err"
      echo "✅ [$REPO_NAME#$PR_NUMBER] done → $OUT_FILE"
    ) &
    pr_pids+=($!)
  done

  # `wait "${pids[@]}"` only reports the LAST job's status, so wait on each pid
  # individually and count failures — otherwise a failed PR job is silent.
  local failed=0 pid
  for pid in "${pr_pids[@]}"; do
    if ! wait "$pid"; then
      failed=$((failed + 1))
    fi
  done

  # Sequential cleanup, now that no parallel git activity on this repo is in
  # flight. Errors are non-fatal — the next run's setup self-heals leftovers.
  local idx
  for idx in "${!WORK_DIRS[@]}"; do
    git -C "$LOCAL_REPO" worktree remove --force "${WORK_DIRS[$idx]}" 2>/dev/null || true
    git -C "$LOCAL_REPO" branch -D "${PR_REFS[$idx]}" 2>/dev/null || true
  done

  if [[ $failed -gt 0 ]]; then
    echo "⚠️  [$REPO_NAME] $failed of ${#pr_pids[@]} PR job(s) failed — raw output kept at $WORK_BASE/$REPO_NAME-pr-*.raw.md*"
    return 1
  fi
  echo "🎉 [$REPO_NAME] all PRs in this repo completed"
}

# --- Run every repo group in parallel too ----------------------------------
repo_pids=()
for i in "${!REPOS[@]}"; do
  review_repo "${REPOS[$i]}" "${PR_LISTS[$i]}" &
  repo_pids+=($!)
done
repo_failed=0
for pid in "${repo_pids[@]}"; do
  if ! wait "$pid"; then
    repo_failed=$((repo_failed + 1))
  fi
done

echo
if [[ $repo_failed -gt 0 ]]; then
  echo "⚠️  Reviews completed with errors: $repo_failed of ${#REPOS[@]} repo group(s) had failing PR job(s)."
else
  echo "🎉 All reviews completed across ${#REPOS[@]} repo group(s)."
fi
echo "Each PR's high-confidence findings (≥80, codex-verified) are already posted."
echo "Everything else is saved under $WORK_BASE/*.review.md for manual selection."
echo "Open an interactive Claude Code session and run:"
echo "  /pr-review-drafts"
[[ $repo_failed -gt 0 ]] && exit 1 || exit 0
