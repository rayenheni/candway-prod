"""Regression: no broken HTML comments leaking text onto the page.

In every admin `.html` page, the nested comment pattern
`<!-- <!-- <!-- ADMIN GUARD BYPASSED --> --> -->` caused the
bare text `--> --> -->` to render on screen because the HTML
parser treats the *first* `-->` as the comment closer, leaving
the remaining `-- >` as visible text.

What this file locks
--------------------
1. No file under `pages/admin/` contains the broken nested-comment
   pattern (multiple `<!--` inside a single `<!--` block)
2. Every `ADMIN GUARD BYPASSED` comment is a single-level comment
3. No `.html` file contains unescaped bare `-->` that could leak text

What this file does NOT cover
-----------------------------
* Non-admin pages (check those separately if needed)
* Other comment styles (`{# ... #}` is Jinja2/Twig, not our stack)
"""

from __future__ import annotations

import pathlib
import re

import pytest

_REPO_ROOT = pathlib.Path(__file__).resolve().parents[1]
_ADMIN_PAGES = sorted((_REPO_ROOT / "pages" / "admin").glob("*.html"))


def test_no_admin_page_has_nested_html_comments():
    """No admin page should have `<!-- <! -- <! --` (nested comment
    openers). The HTML spec does not support nested comments, so
    the first `-->` closes everything, leaving the remaining
    `-->` as visible text.
    """
    bad_pattern = re.compile(r"<!--[^>]*<!--")
    for page in _ADMIN_PAGES:
        src = page.read_text(encoding="utf-8")
        assert not bad_pattern.search(src), (
            f"{page.name}: found nested HTML comment (`<!--` inside another `<!--`).\n"
            "This leaks text onto the rendered page."
        )


def test_no_admin_page_has_bare_closing_arrow():
    """No admin page should have bare `-->` that isn't inside a
    valid HTML comment.

    A `-->` is valid only if there's a matching preceding `<!- -`
    with no intervening `-->`. This is hard to distinguish from
    source parsing alone, so we take a simpler approach:
    every `-->` must be preceded by a `<!- -` on the same logical line.
    """
    for page in _ADMIN_PAGES:
        src = page.read_text(encoding="utf-8")
        lines = src.splitlines()
        for i, line in enumerate(lines, 1):
            # Ignore lines that contain a valid complete comment
            # (i.e. `<!-- ... -->`)
            if re.search(r"<!--.*?-->", line):
                continue
            # Any remaining `-->` on this line is suspicious
            if "-->" in line:
                # A DOCTYPE line is OK
                if "<!DOCTYPE" in line:
                    continue
                pytest.fail(
                    f"{page.name}:{i}: bare `-->` outside a valid comment.\n"
                    f"  Line: {line.strip()!r}"
                )


def test_all_admin_pages_have_single_ADMIN_GUARD_BYPASSED():
    """If the `ADMIN GUARD BYPASSED` comment is present, there must
    be exactly one occurrence. (Some pages may not have it, but
    those that do must not double it.)
    """
    for page in _ADMIN_PAGES:
        src = page.read_text(encoding="utf-8")
        matches = re.findall(r"ADMIN GUARD BYPASSED", src)
        if len(matches) > 0:
            assert len(matches) == 1, (
                f"{page.name}: expected exactly 1 'ADMIN GUARD BYPASSED' "
                f"comment, found {len(matches)}"
            )


def test_admin_guard_comment_is_clean_when_present():
    """The `ADMIN GUARD BYPASSED` comment, when present, must be
    of the form `<!-- ADMIN GUARD BYPASSED -->` (single-level, with
    spaces), not `<!--<!--...` or any other broken variant.
    """
    for page in _ADMIN_PAGES:
        src = page.read_text(encoding="utf-8")
        match = re.search(r"(<!--[^!]*?ADMIN GUARD BYPASSED[^>]*?-->)", src)
        if not match:
            continue  # page doesn't have the comment, OK
        comment = match.group(1)
        assert comment == "<!-- ADMIN GUARD BYPASSED -->", (
            f"{page.name}: ADMIN GUARD BYPASSED comment has "
            f"unexpected syntax: {comment!r}"
        )
