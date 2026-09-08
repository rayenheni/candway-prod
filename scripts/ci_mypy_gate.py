#!/usr/bin/env python3
"""mypy regression gate for Candway CI.

Full-repo mypy output is compared against a committed baseline of
per-file, per-error-signature counts. Enforcement is restricted to backend
Python files *changed* by the commit/PR (three-dot diff against BASE_SHA),
so the ~2185 pre-existing legacy errors never block unrelated changes,
while ANY new, duplicated, or raised error in changed code fails the gate.
A whole-repo total count guard acts as a secondary safety net for drift in
unchanged files.

Subcommands
-----------
build  <raw.txt> <baseline.json>
    Parse mypy output (lines of the form
    ``path:line: error: message [error-code]``), aggregate per-file
    per-signature counts (line numbers stripped), and write the baseline.
    cwd must be the repository root.

check  <baseline.json> <raw.txt> [--base SHA]
    Compare current mypy output against the baseline. Only files changed
    since ``SHA`` are enforced per-file; the total count must not exceed the
    baseline total. ``SHA`` defaults to ``git merge-base HEAD``'s parent is
    NOT used -- it must be supplied explicitly (BASE_SHA in CI).

Exit codes
----------
0   pass
1   per-file or total-count regression detected
2   environment/parse failure (never a pass) -- e.g. malformed mypy lines,
    missing/invalid baseline, missing BASE_SHA, git unavailable, empty
    error output; fails closed so a crashed mypy can never pass the gate.

BASE_SHA handling (fail-safe, no silent bypass)
-----------------------------------------------
* missing/empty/whitespace BASE_SHA  -> exit 2 (cannot determine changed set)
* all-zero BASE_SHA (40 x "0")       -> documented "no parent" event (first
  push of a branch). Gate is NOT weakened: every tracked backend .py file
  is treated as changed and enforced against the baseline. (``git ls-files``
  is the empty-tree equivalent -- a two-dot diff against the empty tree
  ``4b825dc...`` would list the same set.)
* otherwise                           -> three-dot diff ``SHA...HEAD``.

Malformed-line handling
-----------------------
A line beginning with ``backend/`` that *_looks like* an error line
(``: error:`` present) but fails the canonical pattern is a *malformed error
line* -> exit 2. Notes, source snippets, carets and the ``Found N errors``
summary are ignored. Empty/missing output with a non-empty baseline also
fails closed (exit 2).
"""

import codecs
import json
import os
import re
import subprocess
import sys

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BACKEND_PREFIX = "backend/"
EMPTY_TREE = "4b825dc642cb6eb9a060e54bf8d69288fbee4904"
ZERO_SHA = "0" * 40

# path:line: error: message [code]
_ERROR_RE = re.compile(r"^(?:backend[/\\][^:]+):\d+: error: (.*)$")
# path:line: note: message
_NOTE_RE = re.compile(r"^(?:backend[/\\][^:]+):\d+: note: .*$")
# looks like a backend error line but is not parseable -> malformed
# (e.g. "backend/x.py:5 error: ..." missing a colon, or "backend/x.py:2:  error: ...")
_MALFORMED_RE = re.compile(r"^backend[/\\][^:]*:.*error:")


def _read_text(path):
    """Read possibly UTF-16/UTF-8 text (PowerShell redirects write UTF-16)."""
    with open(path, "rb") as fh:
        raw = fh.read()
    if raw.startswith(codecs.BOM_UTF16_LE) or raw.startswith(codecs.BOM_UTF16_BE):
        return raw.decode("utf-16", errors="replace")
    text = raw.decode("utf-8", errors="replace")
    if text.startswith("\ufeff"):  # UTF-8 BOM (PowerShell Out-File utf8)
        return text[1:]
    return text


def parse_output(text):
    """Return (counts, malformed_lines).

    counts: {relpath: {signature: count}} with forward slashes.
    """
    counts = {}
    malformed = []
    for line in text.splitlines():
        line = line.rstrip("\r")
        m = _ERROR_RE.match(line)
        if m:
            parts = line.split(":", 2)
            path = parts[0].replace("\\", "/")
            sig = parts[2][7:].strip()  # strip " error: "
            counts.setdefault(path, {})
            counts[path][sig] = counts[path].get(sig, 0) + 1
            continue
        if _NOTE_RE.match(line):
            continue
        if _MALFORMED_RE.match(line):
            malformed.append(line.strip())
    return counts, malformed


def load_baseline(path):
    if not os.path.exists(path):
        return None, f"baseline not found: {path}"
    try:
        with open(path, "r", encoding="utf-8") as fh:
            data = json.load(fh)
    except (ValueError, OSError) as exc:
        return None, f"invalid baseline {path}: {exc}"
    if not isinstance(data, dict):
        return None, f"baseline {path} is not a JSON object"
    return data, None


def resolve_changed(base, root=REPO_ROOT):
    """Return the set of changed backend .py files since `base` (forward slashes).

    Exits 2 (caller) on missing base / git failure.
    """
    if base is None or not base.strip():
        return None, "no BASE_SHA provided (failing closed; cannot determine changed files)"
    base = base.strip()
    if base == ZERO_SHA:
        print("note: all-zero BASE_SHA (branch created by this push); "
              "enforcing the entire backend tree against the baseline")
        cmd = ["git", "-c", "core.quotepath=false", "ls-files", "backend/*.py"]
    else:
        cmd = ["git", "-c", "core.quotepath=false", "diff",
               "--name-only", "--diff-filter=ACMRT", f"{base}...HEAD", "--", "backend/"]
    try:
        proc = subprocess.run(cmd, cwd=root, capture_output=True, text=True)
    except OSError as exc:
        return None, f"git unavailable: {exc}"
    if proc.returncode != 0:
        return None, f"git command failed ({' '.join(cmd)}): {proc.stderr.strip() or proc.stdout.strip()}"
    changed = set()
    for raw in proc.stdout.splitlines():
        path = raw.replace("\\", "/").lstrip("./")
        if path.startswith(BACKEND_PREFIX) and path.endswith(".py"):
            changed.add(path)
    return changed, None


def cmd_build(raw_path, baseline_path):
    try:
        text = _read_text(raw_path)
    except OSError as exc:
        print(f"error: cannot read {raw_path}: {exc}", file=sys.stderr)
        return 2
    counts, malformed = parse_output(text)
    if malformed:
        print("error: refusing to build baseline from malformed mypy output:", file=sys.stderr)
        for line in malformed[:20]:
            print(f"  {line}", file=sys.stderr)
        return 2
    try:
        with open(baseline_path, "w", encoding="utf-8") as fh:
            json.dump(counts, fh, indent=2, sort_keys=True)
    except OSError as exc:
        print(f"error: cannot write {baseline_path}: {exc}", file=sys.stderr)
        return 2
    total = sum(sum(c.values()) for c in counts.values())
    print(f"baseline written: {len(counts)} files, {total} errors -> {baseline_path}")
    return 0


def cmd_check(baseline_path, raw_path, base, root=REPO_ROOT):
    baseline, err = load_baseline(baseline_path)
    if baseline is None:
        print(f"error: {err}", file=sys.stderr)
        return 2

    try:
        text = _read_text(raw_path)
    except OSError as exc:
        print(f"error: cannot read {raw_path}: {exc}", file=sys.stderr)
        return 2
    current, malformed = parse_output(text)
    if malformed:
        print("error: malformed backend error line(s) in mypy output:", file=sys.stderr)
        for line in malformed[:20]:
            print(f"  {line}", file=sys.stderr)
        return 2

    cur_total = sum(sum(c.values()) for c in current.values())
    base_total = sum(sum(c.values()) for c in baseline.values())
    if cur_total == 0 and base_total > 0:
        print("error: mypy reported 0 errors but the baseline has errors. "
              "This usually means mypy crashed produced empty output; failing closed.",
              file=sys.stderr)
        return 2

    changed, err = resolve_changed(base, root)
    if changed is None:
        print(f"error: {err}", file=sys.stderr)
        return 2

    violations = []
    for path in sorted(changed):
        cur = current.get(path, {})
        base = baseline.get(path, {})
        for sig, cnt in sorted(cur.items()):
            base_cnt = base.get(sig, 0)
            label = "NEW" if base_cnt == 0 else f"DUPLICATE/DECAY (was {base_cnt})"
            if cnt > base_cnt:
                violations.append(f"  {path}: {label} [{sig}] now {cnt}")

    total_violations = []
    if cur_total > base_total:
        total_violations.append(
            f"  TOTAL REGRESSION: {cur_total} mypy errors exceed baseline {base_total}")

    if violations or total_violations:
        print(f"mypy regression gate: FAIL ({base_total} baseline / {cur_total} current)")
        for v in violations:
            print(v)
        for v in total_violations:
            print(v)
        print("note: only changed backend files are enforced per-file; "
              "regenerate scripts/mypy_baseline.json in a dedicated commit to accept new debt.")
        return 1

    print(f"mypy regression gate: PASS ({cur_total} <= baseline {base_total}; "
          f"{len(changed)} changed file(s) checked)")
    return 0


def main(argv):
    if len(argv) < 2:
        print(__doc__)
        return 2
    cmd = argv[1]
    if cmd == "build" and len(argv) == 4:
        return cmd_build(argv[2], argv[3])
    if cmd == "check" and len(argv) in (4, 6, 8):
        base = None
        root = REPO_ROOT
        rest = argv[4:]
        while rest:
            flag = rest.pop(0)
            if flag == "--base" and rest:
                base = rest.pop(0)
            elif flag == "--root" and rest:
                root = rest.pop(0)
            else:
                print(f"error: unexpected argument '{flag}'", file=sys.stderr)
                return 2
        return cmd_check(argv[2], argv[3], base, root)
    if cmd in ("build", "check"):
        print(f"error: invalid arguments for '{cmd}': use "
              f"'{cmd} ' + help below", file=sys.stderr)
    print(f"usage: {argv[0]} build <raw.txt> <baseline.json> | "
          f"{argv[0]} check <baseline.json> <raw.txt> [--base SHA] [--root DIR]", file=sys.stderr)
    return 2


if __name__ == "__main__":
    sys.exit(main(sys.argv))