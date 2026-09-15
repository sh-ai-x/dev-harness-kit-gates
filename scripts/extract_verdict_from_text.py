# Originally copied from sh-ai-x/dev-harness-kit@<commit-sha>
# Original path: scripts/extract_verdict_from_text.py (added during gates Phase 4 migration)
# SSOT in the gates repo; copy edits BACK to dev-harness-kit as PRs.
#!/usr/bin/env python3
"""extract_verdict_from_text.py — extract the LAST `Verdict: <Word>` from stdin text.

Used by the maintenance judge workflow's `Extract maintenance verdict`
step to recover the verdict from the most recent claude-prefixed PR
comment. Tolerates both plain-form (`Verdict: Approve`) and Markdown
bold-form (`**Verdict:** Changes Requested`) — the maintenance skill
may emit either.

Mirrors VERDICT_RE_LENIENT from `scripts/verdict_from_comment.py` so
the comment-parsing contract is consistent across all three judges.

Usage:
    cat comment-body.txt | python3 extract_verdict_from_text.py

Prints the verdict word (Approve | Blocked | Changes Requested) on
stdout, or empty string if no match.
"""
from __future__ import annotations

import re
import sys

# Same lenient pattern as scripts/verdict_from_comment.py:VERDICT_RE_LENIENT.
VERDICT_RE = re.compile(
    r"(?:^|\n)\s*\*?\*?Verdict:\*?\*?\s*(Approve|Blocked|Changes Requested)\b"
)


def main() -> int:
    text = sys.stdin.read()
    matches = VERDICT_RE.findall(text)
    if matches:
        # The LAST match wins (matches the maintenance workflow's "latest
        # comment → latest verdict" selection rule in the surrounding jq
        # selector).
        print(matches[-1])
    return 0


if __name__ == "__main__":
    sys.exit(main())
