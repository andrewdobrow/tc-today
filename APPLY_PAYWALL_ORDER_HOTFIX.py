from pathlib import Path
ROOT = Path(__file__).resolve().parent
changed = 0
for path in (ROOT / 'articles').glob('*.html'):
    text = path.read_text(encoding='utf-8')
    updated = text.replace('membership.js?v=1.13.7.13','membership.js?v=1.13.7.14').replace('membership.css?v=1.13.7.13','membership.css?v=1.13.7.14')
    if updated != text:
        path.write_text(updated, encoding='utf-8')
        changed += 1
print(f'Updated membership asset version on {changed} article pages.')
