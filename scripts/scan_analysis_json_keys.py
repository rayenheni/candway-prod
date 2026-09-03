import re
from pathlib import Path

keys = {}
for p in Path('backend').rglob('*.py'):
    try:
        text = p.read_text(encoding='utf-8', errors='ignore')
    except Exception:
        continue
    for m in re.finditer(r'(?:meta|analysis|existing_meta|parsed|app\.analysis_json)\[[\"\\\']([a-z_][a-z0-9_]+)[\"\\\']\]', text):
        k = m.group(1)
        if k in ('class', 'method'):
            continue
        keys[k] = keys.get(k, 0) + 1
for k, v in sorted(keys.items(), key=lambda x: -x[1]):
    print(f'{v:4d}  {k}')
