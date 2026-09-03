"""CI enforcement: ensure single canonical metric source.

Checks:
1. No inline func.count/func.avg/func.sum in routers (allow # noqa)
2. No import from backend.analytics_service
3. No .filter().length for counting in JS (allow // TODO:)

Domain allowlist: non-recruiter routers that legitimately aggregate their own data.
"""

import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Directories/file patterns to skip (non-recruiter domains with their own data models)
SKIP_DIRS = [
    "courses",
    "mentor",
    "messages",
    "prompt_management",
    "admin",
    "copilot_admin",
]


def _is_skipped(path: str) -> bool:
    norm = path.replace("\\", "/")
    for skip in SKIP_DIRS:
        if f"/{skip}/" in norm or norm.endswith(f"/{skip}.py"):
            return True
    return False


def check_inline_sql() -> list[str]:
    violations = []
    routers_dir = os.path.join(ROOT, "backend", "routers")
    for root, _dirs, files in os.walk(routers_dir):
        for f in files:
            if not f.endswith(".py") or f.startswith("__"):
                continue
            path = os.path.join(root, f)
            if _is_skipped(path):
                continue
            with open(path, encoding="utf-8", errors="ignore") as fh:
                lines = fh.readlines()
            for i, line in enumerate(lines, 1):
                stripped = line.strip()
                if "# noqa" in stripped:
                    continue
                if re.search(r"func\.(count|avg|sum)\s*\(", stripped):
                    violations.append(f"  {path}:{i}: {stripped[:100]}")
    return violations


def check_analytics_import() -> list[str]:
    violations = []
    routers_dir = os.path.join(ROOT, "backend", "routers")
    for root, _dirs, files in os.walk(routers_dir):
        for f in files:
            if not f.endswith(".py") or f.startswith("__"):
                continue
            path = os.path.join(root, f)
            if _is_skipped(path):
                continue
            with open(path, encoding="utf-8", errors="ignore") as fh:
                content = fh.read()
            if "from backend.analytics_service import" in content:
                violations.append(f"  {path}: imports archived analytics_service")
    return violations


def check_js_filter_length() -> list[str]:
    violations = []
    js_dir = os.path.join(ROOT, "js")
    for root, _dirs, files in os.walk(js_dir):
        for f in files:
            if not f.endswith(".js"):
                continue
            path = os.path.join(root, f)
            with open(path, encoding="utf-8", errors="ignore") as fh:
                lines = fh.readlines()
            for i, line in enumerate(lines, 1):
                stripped = line.strip()
                if "TODO" in stripped or "// noqa" in stripped:
                    continue
                # Check if a TODO exists within 4 preceding lines
                has_todo_nearby = any(
                    "TODO" in lines[j - 1] for j in range(max(1, i - 4), i)
                )
                if has_todo_nearby:
                    continue
                if re.search(r"\.filter\([^)]*\)\.length", stripped):
                    violations.append(f"  {path}:{i}: {stripped[:100]}")
    return violations


def main():
    exit_code = 0

    sql_issues = check_inline_sql()
    if sql_issues:
        print("VIOLATION: Inline SQL aggregation in routers (use MetricsRepository):")
        for v in sql_issues:
            print(v)
        print(f"\nTotal: {len(sql_issues)} violations")
        exit_code = 1
    else:
        print("PASS: No inline SQL aggregation in routers")

    import_issues = check_analytics_import()
    if import_issues:
        print("\nVIOLATION: Archived analytics_service still imported:")
        for v in import_issues:
            print(v)
        exit_code = 1
    else:
        print("PASS: No imports from archived analytics_service")

    js_issues = check_js_filter_length()
    if js_issues:
        print(
            "\nVIOLATION: .filter().length used for counting in JS (use cached values):"
        )
        for v in js_issues:
            print(v)
        print(f"\nTotal: {len(js_issues)} violations")
        exit_code = 1
    else:
        print("PASS: No .filter().length counting in JS")

    sys.exit(exit_code)


if __name__ == "__main__":
    main()
