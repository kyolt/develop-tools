# pr-review

Version-controlled copy of the PR review tooling. Layout mirrors `~/.claude/`,
so restoring = copy each folder back to the same path under `~/.claude/`.

The scripts hardcode `$HOME/.claude/...` paths, so install location matters.

| Here | Install to |
|------|------------|
| `skills/pr-review/`, `skills/pr-review-post/`, `skills/pr-review-select/` | `~/.claude/skills/` |
| `commands/pr-review-drafts.md` | `~/.claude/commands/` |
| `scripts/pr_confidence_review.py`, `scripts/findings-addendum.template.md`, `scripts/verdict-schema.json` | `~/.claude/scripts/` |
| `review-rules/` (incl. `observ/`) | `~/.claude/review-rules/` |
| `review-prs.sh` | `~/.claude/` |
| `PR_reviews.md` | `~/.claude/` |

## Restore

```bash
SRC=. ; DST="$HOME/.claude"
cp -R "$SRC/skills/." "$DST/skills/"
cp "$SRC/commands/"pr-review*.md "$DST/commands/"
cp "$SRC/scripts/." "$DST/scripts/" 2>/dev/null; cp "$SRC"/scripts/* "$DST/scripts/"
cp -R "$SRC/review-rules/." "$DST/review-rules/"
cp "$SRC/review-prs.sh" "$SRC/PR_reviews.md" "$DST/"
chmod +x "$DST/review-prs.sh" "$DST/scripts/pr_confidence_review.py"
```

## Flow

`review-prs.sh` = headless batch entry. Loads rules from `review-rules/`
(`_base.md` + per-repo `<repo>.md` or `<repo>/*.md`), generates drafts,
runs `scripts/pr_confidence_review.py` (adversarial verify, conf ≥80 auto-posts),
leaves the rest for `/pr-review-drafts`. Interactive review = `pr-review` skill.
