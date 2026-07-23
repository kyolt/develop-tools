
---

After the "Candidate Review Comments" section, add one more section, exactly:

## Machine-Readable Findings

Followed by a single fenced json code block containing an array with ONE
object per candidate comment (same content, machine-readable form):

===JSON_FENCE_OPEN===
[
  {
    "id": 1,
    "path": "app/services/user.py",
    "line": 128,
    "severity": "must",
    "type": "logic",
    "comment": "This early return bypasses validation when the payload is empty.",
    "why": "Downstream code assumes validated input and may fail later with a less clear error.",
    "suggested_fix": "Validate before the early-return path."
  }
]
===JSON_FENCE_CLOSE===

Field rules:
- id must match the number of the comment in "Candidate Review Comments".
- line is the single most relevant line number (integer, not a range).
- If a comment has no resolvable file/line, set path to "unknown" and line to null.
- suggested_fix may be null if there is none.
- If there are zero candidate comments, output an empty array.
