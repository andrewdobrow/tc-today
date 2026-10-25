#!/usr/bin/env python3
"""Surgically amend CURRENT scripts/generate.py; refuse ambiguous revisions.

Only broadens the mirrored-source RSS validation in one explicitly authorized
case: a durable custom article uses the same TCT CDN URL in its three persisted
image fields. Normal publisher mirrors still require external source provenance.
"""
import ast
from pathlib import Path

path = Path(__file__).resolve().parent / 'generate.py'
src = path.read_text(encoding='utf-8')
marker = '                    from tct_engine.custom_hosted_social_image import is_editor_authored_custom_hosted_image'
if marker not in src:
    anchor = '''                if not mirror_ok:
                    issues.append({
                        "slug": slug,
                        "reason": "mirrored_source_authority_not_persisted_to_archive",'''
    assert src.count(anchor) == 1, 'Refusing edit: RSS mirrored-source validation location changed'
    replacement = '''                if not mirror_ok:
                    # User-supplied custom editorial photos may be first-party CDN
                    # assets, not publisher mirrors. Require persisted exact-image
                    # agreement and durable custom identity before allowing them.
                    from tct_engine.custom_hosted_social_image import is_editor_authored_custom_hosted_image
                    mirror_ok = is_editor_authored_custom_hosted_image(
                        row, actual,
                        absolute_image_url=_absolute_image_url,
                        is_tct_image=_is_tct_mirrored_image_url,
                    )
                if not mirror_ok:
                    issues.append({
                        "slug": slug,
                        "reason": "mirrored_source_authority_not_persisted_to_archive",'''
    src = src.replace(anchor, replacement, 1)
    ast.parse(src, filename=str(path))
    path.write_text(src, encoding='utf-8')
else:
    assert src.count(marker) == 1, 'Refusing edit: duplicated custom RSS guard'
    ast.parse(src, filename=str(path))
print('PASS: custom-hosted image RSS exception installed on current generator (idempotent)')
