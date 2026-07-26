#!/usr/bin/env python3
"""Install or update the prepared TCT hurricane product guide.

This script follows TCT's exact-headline custom publishing contract:
- exact headline already present -> replace that JSON object in place
- any other headline -> preserve it unchanged
- headline not present -> append the new article
"""
from __future__ import annotations

import argparse
import json
import shutil
from datetime import datetime
from pathlib import Path


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument('--target', default='custom_articles.json', help='Path to TCT custom_articles.json')
    parser.add_argument(
        '--entry',
        default=str(Path(__file__).resolve().parents[1] / 'content' / 'hurricane-season-ready-product-guide.json'),
        help='Prepared product guide JSON file',
    )
    parser.add_argument('--dry-run', action='store_true')
    args = parser.parse_args()

    target = Path(args.target)
    entry_path = Path(args.entry)
    payload = json.loads(entry_path.read_text(encoding='utf-8'))
    if not isinstance(payload, list) or len(payload) != 1 or not isinstance(payload[0], dict):
        raise SystemExit('Entry file must contain exactly one JSON article object in an array.')
    article = payload[0]
    headline = str(article.get('headline') or '').strip()
    if not headline:
        raise SystemExit('Prepared article is missing headline.')

    if target.exists():
        current = json.loads(target.read_text(encoding='utf-8'))
        if not isinstance(current, list):
            raise SystemExit(f'{target} must contain a JSON array.')
    else:
        current = []

    exact_indexes = [
        idx for idx, row in enumerate(current)
        if isinstance(row, dict) and str(row.get('headline') or '').strip() == headline
    ]
    if len(exact_indexes) > 1:
        raise SystemExit(f'Refusing to modify {target}: multiple exact-headline entries already exist.')

    action = 'append'
    if exact_indexes:
        current[exact_indexes[0]] = article
        action = 'exact-headline update'
    else:
        current.append(article)

    rendered = json.dumps(current, indent=2, ensure_ascii=False) + '\n'
    json.loads(rendered)  # final validation
    print(f'{action}: {headline}')
    print(f'products: {len(article.get("products") or [])}')
    if args.dry_run:
        return 0

    if target.exists():
        stamp = datetime.now().strftime('%Y%m%d-%H%M%S')
        backup = target.with_suffix(target.suffix + f'.{stamp}.bak')
        shutil.copy2(target, backup)
        print(f'backup: {backup}')
    target.write_text(rendered, encoding='utf-8')
    print(f'wrote: {target}')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
