"""
Audit the codebase for ``Column.is None`` patterns that compile
to ``WHERE false`` (the Python ``is`` operator always evaluates
to False at class-descriptor level, defeating the SQL filter).
"""
import re
from pathlib import Path

pattern = re.compile(
    r"\.filter\(\s*([A-Za-z_][A-Za-z0-9_\.]*\.[A-Za-z_][A-Za-z0-9_]*)\s+is\s+None\s*\)"
)
matches_by_file = {}
for p in Path("backend").rglob("*.py"):
    text = p.read_text(encoding="utf-8", errors="ignore")
    for i, line in enumerate(text.splitlines(), 1):
        for m in pattern.finditer(line):
            matches_by_file.setdefault(str(p), []).append((i, line.strip()))

for fp, lst in matches_by_file.items():
    print(fp)
    for ln, txt in lst:
        print(f"  line {ln}: {txt}")
print()
print(f"Total files affected: {len(matches_by_file)}")
print(f"Total occurrences: {sum(len(v) for v in matches_by_file.values())}")
