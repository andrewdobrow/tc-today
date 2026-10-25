#!/usr/bin/env python3
"""Apply one surgical, idempotent insertion to CURRENT scripts/generate.py.

Run in the checked-out HEAD, never replace a 2 MB generator with an old ZIP copy.
Stops if expected integration points have moved or would be ambiguous.
"""
from pathlib import Path
import ast

path = Path(__file__).resolve().parent / 'generate.py'
src = path.read_text(encoding='utf-8')
marker = '    # Named-death custom authority: exact subject, same death date and agency.'
if marker not in src:
    start = src.find('def _durable_custom_identity_match(candidate, authority, *, precomputed=None):')
    end = src.find('\ndef ', start + 5)
    if start < 0 or end < 0:
        raise SystemExit('Refusing edit: durable custom identity function not found exactly once')
    chunk = src[start:end]
    anchor = '    if _westmoreland_alf_custom_authority_match(candidate, authority):'
    assert chunk.count(anchor) == 1, 'Refusing edit: expected custom identity insertion point changed'
    insertion = '''    # Named-death custom authority: exact subject, same death date and agency.
    # This preempts headline-angle drift without merging different relatives.
    from tct_engine.custom_named_death_identity import same_named_death_as_custom
    named_death_match, named_death_key = same_named_death_as_custom(candidate, authority)
    if named_death_match:
        return True, named_death_key

'''
    chunk = chunk.replace(anchor, insertion + anchor, 1)
    src = src[:start] + chunk + src[end:]

# In a semantic update, preserve an existing authoritative custom's own image,
# rather than replacing it with the image used by an incoming news source.
marker_photo = '    # Preserve authoritative custom imagery during verified source updates.'
if marker_photo not in src:
    needle = '''    incoming_source_image = _absolute_image_url(
        (incoming or {}).get("source_image_url") or (incoming or {}).get("image_url")
    )'''
    if src.count(needle) != 1:
        raise SystemExit('Refusing edit: custom image authority location changed')
    replacement = needle + '''
    # Preserve authoritative custom imagery during verified source updates.
    # Manual edits to the custom queue remain the way to change the image.
    if (canonical.get("is_custom") or canonical.get("authoritative_custom")) and _is_real_source_image_url(
        _absolute_image_url(canonical.get("image_url") or canonical.get("source_image_url"))
    ):
        incoming_source_image = ""'''
    src = src.replace(needle, replacement, 1)
ast.parse(src, filename=str(path))
path.write_text(src, encoding='utf-8')
print('PASS: current generator identity + protected image guards installed (idempotent)')
