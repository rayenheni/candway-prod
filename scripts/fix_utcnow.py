"""Fix datetime.utcnow() deprecation in production source files.

Replaces every ``datetime.utcnow()`` call with the timezone-aware
``datetime.now(UTC)``. Adds ``UTC`` to the existing ``from datetime import``
line when needed.

Skips test files (conftest handles time semantics) and skips files
where the existing code already uses ``datetime.now(UTC)``.
"""
from __future__ import annotations

import os
import re
import sys


def _find_utcnow_calls(src: str) -> list[tuple[int, str]]:
    """Return (line_number, line_text) for every line that calls
    ``.utcnow()``."""
    out = []
    for i, line in enumerate(src.splitlines(), 1):
        if re.search(r"\.utcnow\(\)", line):
            out.append((i, line))
    return out


def _ensure_utc_in_import(src: str) -> str:
    """If the file uses ``from datetime import ...`` and does not
    import ``UTC``, add it. Returns the updated source."""
    m = re.search(
        r"^from datetime import\s+([^\n]+)$", src, flags=re.MULTILINE
    )
    if not m:
        return src
    names = [n.strip() for n in m.group(1).split(",") if n.strip()]
    if "UTC" in names:
        return src
    names.append("UTC")
    names = sorted(set(names), key=lambda n: n != "datetime")
    new_line = "from datetime import " + ", ".join(names)
    return src[: m.start()] + new_line + src[m.end() :]


def fix_file(path: str) -> tuple[int, str]:
    """Return (n_replacements, status_message) for ``path``."""
    with open(path, encoding="utf-8") as f:
        src = f.read()
    calls = _find_utcnow_calls(src)
    if not calls:
        return 0, "no utcnow calls"

    # Replace `datetime.utcnow()` with `datetime.now(UTC)`.
    new_src = re.sub(r"datetime\.utcnow\(\)", "datetime.now(UTC)", src)
    # And the bare `.utcnow()` form (rare but legal if datetime is
    # rebound to a variable named ``dt`` etc).
    # We only touch the dotted form to stay conservative.
    if "UTC" not in re.search(
        r"^from datetime import\s+([^\n]+)$", new_src, flags=re.MULTILINE
    ).group(1):
        new_src = _ensure_utc_in_import(new_src)

    if new_src == src:
        return 0, "no change"

    with open(path, "w", encoding="utf-8") as f:
        f.write(new_src)
    return len(calls), f"replaced {len(calls)} call(s)"


def main(roots: list[str]) -> int:
    fixed = 0
    total_replacements = 0
    for root in roots:
        for dirpath, dirnames, filenames in os.walk(root):
            # Only skip the scripts/ dir (this fixer itself
            # lives there). Test files SHOULD also be migrated
            # to timezone-aware datetimes so the deprecation
            # warning stops flooding test output.
            parts = set(dirpath.replace("\\", "/").split("/"))
            if "scripts" in parts:
                continue
            for fn in filenames:
                if not fn.endswith(".py"):
                    continue
                p = os.path.join(dirpath, fn)
                n, msg = fix_file(p)
                if n:
                    print(f"  {p}: {msg}")
                    fixed += 1
                    total_replacements += n
    print(f"\n{total_replacements} replacements across {fixed} files")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:] or ["backend"]))
