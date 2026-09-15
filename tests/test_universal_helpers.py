"""Pin the behavior of the Phase-4 universal helpers.

Covers:
  - scripts/extract_verdict.py
  - scripts/verdict_from_comment.py
  - scripts/extract_verdict_from_text.py

These three are stdlib-only, have no dev-harness-kit imports, and
form the universal verdict-extraction contract the gates repo provides
to its reusable workflows. Tests pin each branch documented in their
docstrings so a no-sync future copy cannot drift silently.
"""
from __future__ import annotations

import io
import json
import pathlib
import subprocess
import sys

import pytest


REPO_ROOT = pathlib.Path(__file__).resolve().parent.parent
SCRIPTS_DIR = REPO_ROOT / "scripts"

EXTRACT_VERDICT = SCRIPTS_DIR / "extract_verdict.py"
VERDICT_FROM_COMMENT = SCRIPTS_DIR / "verdict_from_comment.py"
EXTRACT_VERDICT_FROM_TEXT = SCRIPTS_DIR / "extract_verdict_from_text.py"


def _run(script: pathlib.Path, *args: str, stdin_text: str = "") -> subprocess.CompletedProcess:
    """Invoke a helper script the same way the workflow does and capture output."""
    return subprocess.run(
        [sys.executable, str(script), *args],
        input=stdin_text,
        capture_output=True,
        text=True,
        timeout=10,
    )


# ---------------------------------------------------------------------------
# extract_verdict.py — execution-file parser
# ---------------------------------------------------------------------------


def test_extract_verdict_empty_file_returns_empty(tmp_path):
    f = tmp_path / "empty.json"
    f.write_text("")
    res = _run(EXTRACT_VERDICT, str(f))
    assert res.stdout.strip() == ""


def test_extract_verdict_missing_file_returns_empty(tmp_path):
    res = _run(EXTRACT_VERDICT, str(tmp_path / "does-not-exist.json"))
    assert res.stdout.strip() == ""


def test_extract_verdict_html_returns_empty(tmp_path):
    """HTML/XML payload (network error page, 404) → empty (no false Approve)."""
    f = tmp_path / "html.json"
    f.write_text("<html><body>404 Not Found</body></html>")
    res = _run(EXTRACT_VERDICT, str(f))
    assert res.stdout.strip() == ""


def test_extract_verdict_no_verdict_line_returns_parse_failed(tmp_path):
    """Parseable JSONL with no `Verdict:` line → PARSE_FAILED (hard-fail sentinel)."""
    f = tmp_path / "no_verdict.json"
    f.write_text(
        '{"type":"assistant","message":{"content":[{"type":"text","text":"Looks fine."}]}}\n'
    )
    res = _run(EXTRACT_VERDICT, str(f))
    assert res.stdout.strip() == "PARSE_FAILED"


def test_extract_verdict_last_verdict_wins(tmp_path):
    """Multiple Verdict: lines in the file → the LAST one is the verdict."""
    f = tmp_path / "multi.json"
    f.write_text(
        '{"type":"assistant","message":{"content":[{"type":"text","text":"Verdict: Changes Requested"}]}}\n'
        '{"type":"assistant","message":{"content":[{"type":"text","text":"Verdict: Approve"}]}}\n'
    )
    res = _run(EXTRACT_VERDICT, str(f))
    assert res.stdout.strip() == "Approve"


def test_extract_verdict_blocked(tmp_path):
    f = tmp_path / "blocked.json"
    f.write_text(
        '{"type":"assistant","message":{"content":[{"type":"text","text":"Verdict: Blocked"}]}}\n'
    )
    res = _run(EXTRACT_VERDICT, str(f))
    assert res.stdout.strip() == "Blocked"


def test_extract_verdict_changes_requested(tmp_path):
    f = tmp_path / "cr.json"
    f.write_text(
        '{"type":"assistant","message":{"content":[{"type":"text","text":"Verdict: Changes Requested"}]}}\n'
    )
    res = _run(EXTRACT_VERDICT, str(f))
    assert res.stdout.strip() == "Changes Requested"


def test_extract_verdict_minimax_result_envelope(tmp_path):
    """MINIMAX wrapper emits only `type=result` summary messages (issue #625)."""
    f = tmp_path / "minimax.json"
    f.write_text(
        '{"type":"result","result":"Verdict: Approve"}\n'
    )
    res = _run(EXTRACT_VERDICT, str(f))
    assert res.stdout.strip() == "Approve"


def test_extract_verdict_skips_error_flagged_envelopes(tmp_path):
    """An aborted run's partial summary must NOT satisfy the gate."""
    f = tmp_path / "aborted.json"
    f.write_text(
        '{"type":"assistant","is_error":true,"message":{"content":[{"type":"text","text":"Verdict: Approve"}]}}\n'
        '{"type":"assistant","message":{"content":[{"type":"text","text":"Verdict: Blocked"}]}}\n'
    )
    res = _run(EXTRACT_VERDICT, str(f))
    assert res.stdout.strip() == "Blocked"


def test_extract_verdict_skips_non_candidate_msg_types(tmp_path):
    """user / tool_use / system messages must NOT satisfy the gate."""
    f = tmp_path / "mixed.json"
    f.write_text(
        '{"type":"user","message":{"content":[{"type":"text","text":"Verdict: Approve"}]}}\n'
        '{"type":"assistant","message":{"content":[{"type":"text","text":"Verdict: Blocked"}]}}\n'
    )
    res = _run(EXTRACT_VERDICT, str(f))
    assert res.stdout.strip() == "Blocked"


def test_extract_verdict_with_comments_fallback(tmp_path):
    """When file verdict is PARSE_FAILED AND a comments file is provided,
    recover from the comments."""
    f = tmp_path / "parse_failed.json"
    f.write_text(
        '{"type":"assistant","message":{"content":[{"type":"text","text":"Looks fine."}]}}\n'
    )
    comments = tmp_path / "comments.json"
    comments.write_text(json.dumps([
        {"body": "<!-- dev-kit-verdict-audit --> ignore", "author": {"login": "github-actions[bot]"}},
        {"body": "Verdict: Approve", "author": {"login": "claude"}},
    ]))
    res = _run(EXTRACT_VERDICT, str(f), str(comments))
    assert res.stdout.strip() == "Approve"


# ---------------------------------------------------------------------------
# verdict_from_comment.py — PR-comments scanner
# ---------------------------------------------------------------------------


def _run_stdin(script: pathlib.Path, stdin_text: str, cutoff: str = "") -> subprocess.CompletedProcess:
    env = {"PATH": "/usr/bin:/bin:/usr/local/bin"}
    full_env = {**env, "VERDICT_COMMENT_CUTOFF": cutoff}
    return subprocess.run(
        [sys.executable, str(script)],
        input=stdin_text,
        capture_output=True,
        text=True,
        timeout=10,
        env=full_env,
    )


def test_verdict_from_comment_basic():
    payload = json.dumps([
        {"body": "Verdict: Approve", "author": {"login": "claude"}},
    ])
    res = _run_stdin(VERDICT_FROM_COMMENT, payload)
    assert res.stdout.strip() == "Approve"


def test_verdict_from_comment_bold_form():
    """Bold-wrapped `**Verdict:** <Word>` is the LLM-judge Markdown form."""
    payload = json.dumps([
        {"body": "**Verdict:** Changes Requested", "author": {"login": "claude[bot]"}},
    ])
    res = _run_stdin(VERDICT_FROM_COMMENT, payload)
    assert res.stdout.strip() == "Changes Requested"


def test_verdict_from_comment_skips_non_claude_authors():
    payload = json.dumps([
        {"body": "Verdict: Approve", "author": {"login": "human-reviewer"}},
        {"body": "Verdict: Blocked", "author": {"login": "claude"}},
    ])
    res = _run_stdin(VERDICT_FROM_COMMENT, payload)
    assert res.stdout.strip() == "Blocked"


def test_verdict_from_comment_accepts_legacy_user_login():
    payload = json.dumps([
        {"body": "Verdict: Approve", "user": {"login": "claude"}},
    ])
    res = _run_stdin(VERDICT_FROM_COMMENT, payload)
    assert res.stdout.strip() == "Approve"


def test_verdict_from_comment_accepts_top_level_login():
    payload = json.dumps([
        {"body": "Verdict: Approve", "login": "claude"},
    ])
    res = _run_stdin(VERDICT_FROM_COMMENT, payload)
    assert res.stdout.strip() == "Approve"


def test_verdict_from_comment_no_match_returns_empty():
    payload = json.dumps([
        {"body": "Nothing here", "author": {"login": "claude"}},
    ])
    res = _run_stdin(VERDICT_FROM_COMMENT, payload)
    assert res.stdout.strip() == ""


def test_verdict_from_comment_cutoff_filter():
    """Only comments strictly newer than $VERDICT_COMMENT_CUTOFF count."""
    payload = json.dumps([
        {"body": "Verdict: Changes Requested", "createdAt": "2024-01-01T00:00:00Z", "author": {"login": "claude"}},
        {"body": "Verdict: Approve",            "createdAt": "2024-12-01T00:00:00Z", "author": {"login": "claude"}},
    ])
    res = _run_stdin(VERDICT_FROM_COMMENT, payload, cutoff="2024-06-01T00:00:00Z")
    assert res.stdout.strip() == "Approve"


def test_verdict_from_comment_invalid_json_exits_2():
    res = _run_stdin(VERDICT_FROM_COMMENT, "not-json")
    assert res.returncode == 2


# ---------------------------------------------------------------------------
# extract_verdict_from_text.py — single-text lenient extractor
# ---------------------------------------------------------------------------


def test_extract_verdict_from_text_plain():
    res = _run_stdin(EXTRACT_VERDICT_FROM_TEXT, "Some intro\nVerdict: Approve\nSome outro")
    assert res.stdout.strip() == "Approve"


def test_extract_verdict_from_text_bold():
    res = _run_stdin(EXTRACT_VERDICT_FROM_TEXT, "**Verdict:** Changes Requested\n\nbody")
    assert res.stdout.strip() == "Changes Requested"


def test_extract_verdict_from_text_no_match_returns_empty():
    res = _run_stdin(EXTRACT_VERDICT_FROM_TEXT, "No verdict here at all")
    assert res.stdout.strip() == ""


def test_extract_verdict_from_text_last_match_wins():
    """Multiple verdicts → the LAST one wins."""
    text = "Verdict: Blocked\nMore text\n**Verdict:** Approve"
    res = _run_stdin(EXTRACT_VERDICT_FROM_TEXT, text)
    assert res.stdout.strip() == "Approve"


def test_extract_verdict_from_text_empty_input():
    res = _run_stdin(EXTRACT_VERDICT_FROM_TEXT, "")
    assert res.stdout.strip() == ""
