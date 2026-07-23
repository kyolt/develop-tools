#!/usr/bin/env python3
"""
Post-processes a raw Claude PR-review draft:
  1. Extracts the machine-readable findings JSON block.
  2. Adversarially verifies each finding with `codex exec` (or, if codex is
     unavailable, a Claude self-adversarial second pass — conservative,
     never auto-posts).
  3. Computes a per-finding confidence score from the verdict.
  4. Auto-posts findings with confidence >= AUTO_POST_THRESHOLD as a single
     GitHub review (via `gh api`) — EXCEPT architecture/design findings, which
     are always held for the human to review and reword (see NEVER_AUTO_POST_TYPES).
  5. Writes a final draft file: what got auto-posted, and what's left for
     the human to pick via /pr-review-drafts.

Usage:
  pr_confidence_review.py --repo owner/repo --pr 123 \
      --raw /tmp/claude-reviews/x.raw.md \
      --out /tmp/claude-reviews/x.review.md \
      --cwd /tmp/claude-reviews/x-worktree \
      --branch some-branch
"""
import argparse
import json
import re
import shutil
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

AUTO_POST_THRESHOLD = 80
CONFIDENCE_MAP = {
    "confirmed": 92,
    "confirmed_with_caveat": 77,
    "refuted": 30,
    "unverifiable": 55,
}
SCHEMA_PATH = Path(__file__).parent / "verdict-schema.json"
FINDINGS_HEADING = "## Machine-Readable Findings"
VERIFY_TIMEOUT_SEC = 240


def extract_findings(raw_text: str):
    """Split raw draft into (human_readable_text, findings_list_or_None)."""
    idx = raw_text.find(FINDINGS_HEADING)
    if idx == -1:
        return raw_text, None
    human_part = raw_text[:idx].rstrip()
    rest = raw_text[idx:]
    m = re.search(r"```json\s*(\[.*?\])\s*```", rest, re.DOTALL)
    if not m:
        return human_part, None
    try:
        findings = json.loads(m.group(1))
    except json.JSONDecodeError:
        return human_part, None
    if not isinstance(findings, list):
        return human_part, None
    return human_part, findings


def verify_with_codex(finding: dict, cwd: str, codex_model: str = "") -> dict:
    prompt = (
        "You are an adversarial code reviewer verifying another reviewer's claim "
        "against the ACTUAL code in the current directory (already checked out at "
        "the PR's branch). Default to skepticism — actively try to find reasons "
        "the claim is wrong, already handled, or unreachable.\n\n"
        f"File: {finding.get('path')} (line {finding.get('line')})\n"
        f"Severity/type: {finding.get('severity')} / {finding.get('type')}\n"
        f"Claim: {finding.get('comment')}\n"
        f"Why it allegedly matters: {finding.get('why')}\n"
        f"Suggested fix: {finding.get('suggested_fix') or 'none given'}\n\n"
        "Read the real file and verify. Respond with a verdict: "
        "confirmed (independently verified, clear evidence), "
        "confirmed_with_caveat (likely real, some uncertainty), "
        "refuted (evidence this is NOT real), or "
        "unverifiable (can't determine from available code)."
    )
    out_file = Path(cwd) / f".codex-verdict-{finding.get('id', 'x')}.json"
    cmd = ["codex", "exec", "--skip-git-repo-check", "--sandbox", "read-only"]
    if codex_model:
        cmd += ["--model", codex_model]
    cmd += ["--output-schema", str(SCHEMA_PATH), "-o", str(out_file), prompt]
    try:
        subprocess.run(
            cmd,
            cwd=cwd,
            stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            timeout=VERIFY_TIMEOUT_SEC,
            check=False,
        )
        verdict = json.loads(out_file.read_text())
        if verdict.get("verdict") not in CONFIDENCE_MAP:
            raise ValueError(f"unexpected verdict: {verdict}")
        return verdict
    except Exception as e:
        return {"verdict": "unverifiable", "reasoning": f"codex verification failed: {e}"}
    finally:
        out_file.unlink(missing_ok=True)


def verify_with_claude_fallback(finding: dict, cwd: str) -> dict:
    """Used only when codex is unavailable. Result is informational —
    the caller must NOT auto-post from this path."""
    prompt = (
        "Adversarially re-check this PR review finding against the actual code "
        "in the current directory. Try to refute it; default to skepticism.\n\n"
        f"File: {finding.get('path')} (line {finding.get('line')})\n"
        f"Claim: {finding.get('comment')}\n"
        f"Why: {finding.get('why')}\n\n"
        'Reply with ONLY one line of JSON: '
        '{"verdict": "confirmed|confirmed_with_caveat|refuted|unverifiable", "reasoning": "..."}'
    )
    try:
        proc = subprocess.run(
            ["claude", "--print", "--dangerously-skip-permissions"],
            cwd=cwd,
            input=prompt,
            capture_output=True,
            text=True,
            timeout=VERIFY_TIMEOUT_SEC,
            check=False,
        )
        m = re.search(r"\{.*\}", proc.stdout, re.DOTALL)
        verdict = json.loads(m.group(0)) if m else {}
        if verdict.get("verdict") not in CONFIDENCE_MAP:
            raise ValueError(f"unparseable verdict: {proc.stdout[:200]}")
        return verdict
    except Exception as e:
        return {"verdict": "unverifiable", "reasoning": f"claude fallback verification failed: {e}"}


def confidence_for(verdict: dict) -> int:
    return CONFIDENCE_MAP.get(verdict.get("verdict"), 50)


# Types that are always left for the human to review and reword — design-level
# judgment that shouldn't be posted by a bot even when confidence is high.
NEVER_AUTO_POST_TYPES = {"architecture"}


def is_auto_eligible(finding: dict, verdict: dict) -> bool:
    if finding.get("type") in NEVER_AUTO_POST_TYPES:
        return False
    return confidence_for(verdict) >= AUTO_POST_THRESHOLD


def gh(*args, input_text=None):
    return subprocess.run(
        ["gh", *args], input=input_text, capture_output=True, text=True, check=False
    )


def format_body(f: dict) -> str:
    lines = [f"**[{f.get('severity')} · {f.get('type')}]** {f.get('comment', '').strip()}"]
    why = f.get("why")
    if why:
        lines.append(f"\n_{why.strip()}_")
    fix = f.get("suggested_fix")
    if fix:
        lines.append(f"\n**Suggested:** {fix.strip()}")
    return "\n".join(lines)


def format_body_with_location(f: dict) -> str:
    """Compact form used when a finding is placed in the review body rather than
    inline (because its line isn't part of the PR diff) — includes the location."""
    parts = [
        f"**[{f.get('severity')} · {f.get('type')}]** `{f.get('path')}:{f.get('line')}` — "
        f"{f.get('comment', '').strip()}"
    ]
    if f.get("why"):
        parts.append(f"_{f['why'].strip()}_")
    if f.get("suggested_fix"):
        parts.append(f"**Suggested:** {f['suggested_fix'].strip()}")
    return "\n  ".join(parts)


def get_commentable_lines(repo: str, pr: str):
    """Return {path: set(new_side_line_numbers)} for every line that appears in
    the PR's unified diff (added + context lines), or None if the diff can't be
    fetched. GitHub's line-based review API only accepts inline comments anchored
    to such lines; anything else makes the *whole* review 422."""
    res = gh("pr", "diff", str(pr), "--repo", repo)
    if res.returncode != 0 or not res.stdout:
        return None
    commentable: dict = {}
    cur_path = None
    new_ln = None
    for raw in res.stdout.splitlines():
        if raw.startswith("diff --git"):
            cur_path, new_ln = None, None
        elif raw.startswith("+++ "):
            p = raw[4:].strip()
            if p == "/dev/null":
                cur_path = None
            else:
                cur_path = p[2:] if p.startswith("b/") else p
                commentable.setdefault(cur_path, set())
        elif raw.startswith("@@"):
            m = re.match(r"@@ -\d+(?:,\d+)? \+(\d+)(?:,\d+)? @@", raw)
            new_ln = int(m.group(1)) if m else None
        elif new_ln is not None and cur_path is not None:
            if raw.startswith("+"):
                commentable[cur_path].add(new_ln)
                new_ln += 1
            elif raw.startswith("-") or raw.startswith("\\"):
                pass
            elif raw.startswith(" "):
                commentable[cur_path].add(new_ln)
                new_ln += 1
            else:
                new_ln = None  # left the hunk
    return commentable


def _submit_review(repo: str, pr: str, commit_id: str, body: str, comments: list):
    payload = {"commit_id": commit_id, "body": body, "event": "COMMENT", "comments": comments}
    return gh("api", f"repos/{repo}/pulls/{pr}/reviews", "-X", "POST", "--input", "-",
              input_text=json.dumps(payload))


AUTO_HEADER = ("🤖 Automated review — high-confidence findings below, "
               "independently verified via adversarial check (Codex).")


def post_auto_findings(repo: str, pr: str, findings: list, dry_run: bool = False) -> tuple:
    """Returns (ok: bool, message: str).

    Splits findings into inline comments (location is part of the PR diff) and
    body-only findings (no location, or a line outside the diff). Posting a line
    that isn't in the diff makes GitHub reject the entire review with 422, so
    those are folded into the review body instead of dropped."""
    if dry_run:
        return True, f"[DRY RUN] would post {len(findings)} finding(s) — nothing actually sent"
    sha_res = gh("api", f"repos/{repo}/pulls/{pr}", "--jq", ".head.sha")
    if sha_res.returncode != 0:
        return False, f"could not resolve head sha: {sha_res.stderr.strip()}"
    commit_id = sha_res.stdout.strip()

    commentable = get_commentable_lines(repo, pr)

    inline, body_only = [], []
    for f in findings:
        path, line = f.get("path"), f.get("line")
        if not path or not line or path == "unknown":
            body_only.append(f)  # no resolvable location
            continue
        ln = int(str(line).split("-")[-1])
        # When the diff couldn't be fetched (commentable is None) we don't filter
        # and fall back to attempting inline for everything (old behaviour).
        if commentable is not None and ln not in commentable.get(path, ()):
            body_only.append(f)  # line not in the PR diff -> would 422 inline
            continue
        inline.append({"path": path, "line": ln, "side": "RIGHT", "body": format_body(f)})

    body_parts = [AUTO_HEADER]
    if body_only:
        body_parts.append("\n**Findings outside this PR's diff (can't be anchored to a line):**\n")
        body_parts += [f"- {format_body_with_location(f)}" for f in body_only]
    review_body = "\n".join(body_parts)

    res = _submit_review(repo, pr, commit_id, review_body, inline)
    if res.returncode == 0:
        parts = []
        if inline:
            parts.append(f"{len(inline)} inline")
        if body_only:
            parts.append(f"{len(body_only)} in review body (out-of-diff)")
        return True, "posted " + (" + ".join(parts) if parts else "0 comment(s)")

    # Inline anchoring still rejected (edge case beyond diff-line membership).
    # Retry once with every finding in the body so nothing is silently dropped.
    err = res.stderr.strip()
    if inline:
        all_body = [AUTO_HEADER, "\n**Findings (inline anchoring failed — listed here):**\n"]
        all_body += [f"- {format_body_with_location(f)}" for f in findings]
        retry = _submit_review(repo, pr, commit_id, "\n".join(all_body), [])
        if retry.returncode == 0:
            return True, f"posted {len(findings)} finding(s) in review body (inline post 422'd: {err})"
    return False, f"gh api post failed: {err}"


def render_output(repo, pr, branch, human_part, findings, results, auto_ok, auto_msg, no_findings_note=None):
    out = [f"# Review draft — {repo} PR #{pr} ({branch})"]
    out.append("")
    out.append(human_part.strip() if human_part.strip() else "_(no summary text captured)_")
    out.append("")
    out.append("---")

    if no_findings_note:
        out.append(f"\n> ⚠️ {no_findings_note}\n")
        return "\n".join(out)

    auto = [(f, r) for f, r in results if is_auto_eligible(f, r)]
    manual = [(f, r) for f, r in results if not is_auto_eligible(f, r)]

    out.append(f"\n## ✅ Auto-Posted (confidence ≥ {AUTO_POST_THRESHOLD})\n")
    if not auto:
        out.append("_None met the auto-post threshold._")
    else:
        status = f"Posted: {auto_msg}" if auto_ok else f"⚠️ Posting failed ({auto_msg}) — treat these as needs-review instead:"
        out.append(f"_{status}_\n")
        for f, r in auto:
            out.append(f"- **[{confidence_for(r)}%]** `{f.get('path')}:{f.get('line')}` — {f.get('comment')}")
            out.append(f"  - codex verdict: `{r.get('verdict')}` — {r.get('reasoning')}")
        if not auto_ok:
            manual = auto + manual  # fall back to manual if posting failed

    out.append(f"\n## 🔎 Needs Your Review (confidence < {AUTO_POST_THRESHOLD})\n")
    if not manual:
        out.append("_Nothing left — everything met the auto-post bar._")
    else:
        out.append("Run `/pr-review-drafts` to select which of these to post.\n")
        n_arch = sum(1 for f, _ in manual if f.get("type") in NEVER_AUTO_POST_TYPES)
        if n_arch:
            out.append(f"> 🏛️ {n_arch} architecture/design finding(s) below are held for you "
                       "regardless of confidence — review the reasoning and reword before posting.\n")
        for i, (f, r) in enumerate(manual, 1):
            held = " · 🏛️ held: architecture (reword before posting)" if f.get("type") in NEVER_AUTO_POST_TYPES else ""
            out.append(f"**[{i}]** confidence {confidence_for(r)}% (codex: `{r.get('verdict')}`){held}")
            out.append(f"- `type: {f.get('type')}`")
            out.append(f"- `severity: {f.get('severity')}`")
            out.append(f"- `location: {f.get('path')}:{f.get('line')}`")
            out.append(f"- `comment: {f.get('comment')}`")
            if f.get("why"):
                out.append(f"- `why: {f.get('why')}`")
            if f.get("suggested_fix"):
                out.append(f"- `suggested_fix: {f.get('suggested_fix')}`")
            out.append(f"- `verification: {r.get('reasoning')}`")
            out.append("")

    return "\n".join(out)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--repo", required=True)
    ap.add_argument("--pr", required=True)
    ap.add_argument("--branch", default="")
    ap.add_argument("--raw", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--cwd", required=True)
    ap.add_argument("--dry-run", action="store_true", help="verify + score but never actually call gh api post")
    ap.add_argument("--codex-model", default="", help="model passed to `codex exec --model` for verification")
    args = ap.parse_args()

    raw_text = Path(args.raw).read_text(errors="replace")
    human_part, findings = extract_findings(raw_text)

    if not findings:
        Path(args.out).write_text(render_output(
            args.repo, args.pr, args.branch, human_part or raw_text, [], [], False, "",
            no_findings_note="Could not parse machine-readable findings from the draft "
                              "(model may not have followed the format, or found nothing to flag). "
                              "Showing raw draft above only — no confidence scoring or auto-post ran."
        ))
        print(f"⚠️  [{args.repo}#{args.pr}] no findings JSON — skipped confidence pipeline")
        return

    codex_available = shutil.which("codex") is not None

    def verify(f):
        if codex_available:
            return verify_with_codex(f, args.cwd, args.codex_model)
        return verify_with_claude_fallback(f, args.cwd)

    results = []
    with ThreadPoolExecutor(max_workers=4) as pool:
        futs = {pool.submit(verify, f): f for f in findings}
        for fut in as_completed(futs):
            f = futs[fut]
            results.append((f, fut.result()))
    # keep original order
    order = {id(f): i for i, f in enumerate(findings)}
    results.sort(key=lambda pair: order.get(id(pair[0]), 0))

    if not codex_available:
        # Conservative fallback: never auto-post without an independent
        # (codex) verifier. Force everything below the threshold.
        for f, r in results:
            r["reasoning"] = "⚠️ codex unavailable — Claude self-review only, not eligible for auto-post. " + r.get("reasoning", "")
        auto_candidates = []
    else:
        auto_candidates = [f for f, r in results if is_auto_eligible(f, r)]

    auto_ok, auto_msg = (False, "")
    if auto_candidates:
        auto_ok, auto_msg = post_auto_findings(args.repo, args.pr, auto_candidates, dry_run=args.dry_run)

    Path(args.out).write_text(render_output(
        args.repo, args.pr, args.branch, human_part, findings, results, auto_ok, auto_msg
    ))
    n_auto = len(auto_candidates) if auto_ok else 0
    n_manual = len(findings) - n_auto
    label = "codex" if codex_available else "claude-fallback (no auto-post)"
    print(f"✅ [{args.repo}#{args.pr}] verified via {label}: {n_auto} auto-posted, {n_manual} need review")


if __name__ == "__main__":
    sys.exit(main())
