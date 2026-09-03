"""P0-07 FIX test: ``manage_marketing`` is the right permission for
sending bulk marketing email, not ``manage_content``.

This is a smoke test that asserts the string literal used in
``routers/admin/marketing.py::send_marketing_campaign`` is the
expected permission. A code-review test rather than a behaviour
test, but it locks the regression in place.
"""


def test_marketing_uses_manage_marketing_permission():
    from pathlib import Path

    src = Path("backend/routers/admin/marketing.py").read_text(encoding="utf-8")
    # The bulk-send endpoint must check the dedicated permission.
    assert '"manage_marketing"' in src or "'manage_marketing'" in src
    # The active permission check inside send_marketing_campaign
    # must use manage_marketing and not manage_content. We split
    # on the next def so the assertion only inspects the
    # send_campaign block, not the comment that explains the old
    # bug.
    send_block = src.split("def send_marketing_campaign")[1].split("def ")[0]
    assert "manage_marketing" in send_block
    # Strip comments and docstrings from the block before checking
    # for manage_content (the comment deliberately mentions the
    # old name to explain the fix).
    code_only = "\n".join(
        line for line in send_block.splitlines()
        if line.strip() and not line.strip().startswith("#")
    )
    assert "manage_content" not in code_only


def test_admin_common_declares_manage_marketing_field():
    from pathlib import Path

    src = Path("backend/routers/admin/common.py").read_text(encoding="utf-8")
    assert "manage_marketing" in src
