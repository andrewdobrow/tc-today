#!/usr/bin/env python3
"""Install source-backed county jurisdiction guards into the current generator."""
from __future__ import annotations
from pathlib import Path
import os, re, tempfile, py_compile

ROOT = Path(__file__).resolve().parents[1]
PATH = ROOT / "scripts" / "generate.py"
MARKER = "# v1.13.1.6: source-backed county jurisdiction authority"
COUNTY_HELPER = r'''

# v1.13.1.6: source-backed county jurisdiction authority
_COUNTY_SOURCE_TERMS = {
    "martin": ("martin county", "stuart", "jensen beach", "palm city", "hobe sound", "port salerno", "jupiter island", "indiantown", "sewall's point", "rio"),
    "st_lucie": ("st. lucie county", "st lucie county", "port st. lucie", "port st lucie", "fort pierce", "st. lucie west", "tradition"),
    "indian_river": ("indian river county", "vero beach", "sebastian", "fellsmere", "wabasso", "gifford", "orchid"),
}
_OUTSIDE_TREASURE_COAST_TERMS = (
    "palm beach county", "west palm beach", "royal palm beach", "palm beach gardens",
    "delray beach", "boca raton", "boynton beach", "lake worth", "wellington, florida",
    "riviera beach", "loxahatchee", "belle glade", "pahokee", "broward county",
    "miami-dade", "miami dade", "okeechobee county", "brevard county",
)

def _source_only_jurisdiction_blob(source):
    source = source if isinstance(source, dict) else {}
    values = (
        source.get("source_title"), source.get("title"), source.get("source_headline"),
        source.get("article_text"), source.get("source_text"), source.get("source_summary"),
        source.get("summary"), source.get("link"), source.get("source_url"), source.get("feed_url"),
    )
    return re.sub(r"\s+", " ", " ".join(str(v or "") for v in values)).lower()

def _source_jurisdiction_diagnostics(item, source=None):
    item = item if isinstance(item, dict) else {}
    source = source if isinstance(source, dict) else item
    category_key = str(item.get("category_key") or source.get("category_key") or "")
    required_terms = _COUNTY_SOURCE_TERMS.get(category_key)
    if not required_terms:
        return {"required": False, "passed": True, "missing": []}
    source_blob = _source_only_jurisdiction_blob(source)
    local_hits = [term for term in required_terms if term in source_blob]
    outside_hits = [term for term in _OUTSIDE_TREASURE_COAST_TERMS if term in source_blob]
    missing = []
    if not local_hits:
        missing.append("generated_jurisdiction_not_supported_by_source")
    if outside_hits and not local_hits:
        missing.append("source_jurisdiction_conflicts_with_generated_county")
    return {
        "required": True,
        "passed": not missing,
        "category_key": category_key,
        "local_source_hits": local_hits,
        "outside_source_hits": outside_hits,
        "missing": missing,
    }
'''

COUNTY_FAST = r'''

def _county_zero_candidate_fast_recovery(category_key, headlines):
    """Skip model generation when a county has no source-backed hero candidate."""
    if category_key not in {"martin", "st_lucie", "indian_river"}:
        return False
    return not any(_hero_eligible(category_key, item) for item in (headlines or []))
'''

MAIN_BRANCH = r'''
        if _county_zero_candidate_fast_recovery(cat_key, headlines):
            print(
                f"  County source-authority recovery: no deterministic {cat_config['label']} "
                "hero candidate; skipping Claude and using verified archive recovery"
            )
            _finalize_category_generation_record(
                _category_record,
                "county_zero_candidate_archive_recovery",
                _category_started,
                archive_recovery_requested=True,
                failure_code="no_source_backed_county_hero_candidates",
                failure_summary=(
                    f"Selected {cat_config['label']} source pool contained no source-backed county hero candidate"
                ),
            )
            continue
'''

def replace_once(src, old, new, label):
    if old not in src:
        raise RuntimeError(f"Cannot install {label}: anchor missing")
    return src.replace(old, new, 1)

def patch(src: str) -> tuple[str, bool]:
    original = src
    if MARKER not in src:
        anchor = "\ndef _article_framing_diagnostics(item, source=None):"
        src = replace_once(src, anchor, COUNTY_HELPER + anchor, "jurisdiction diagnostics")
    if "def _county_zero_candidate_fast_recovery" not in src:
        anchor = "\n\n# Hero selection is stricter than card inclusion."
        src = replace_once(src, anchor, COUNTY_FAST + anchor, "county fast recovery")
    if "item[\"category_key\"] = category_key" not in src:
        anchor = '                item["source_title"] = source.get("title", "")\n'
        src = replace_once(src, anchor, anchor + '                item["category_key"] = category_key\n', "generated item category stamp")
    if 'source_jurisdiction_diag = _source_jurisdiction_diagnostics(item, source)' not in src:
        src = replace_once(
            src,
            '    source_focus_diag = _source_focus_diagnostics(item, source)\n',
            '    source_focus_diag = _source_focus_diagnostics(item, source)\n    source_jurisdiction_diag = _source_jurisdiction_diagnostics(item, source)\n',
            "framing jurisdiction call",
        )
        src = replace_once(
            src,
            '        + list(source_focus_diag.get("missing") or [])\n',
            '        + list(source_focus_diag.get("missing") or [])\n        + list(source_jurisdiction_diag.get("missing") or [])\n',
            "framing jurisdiction missing",
        )
        src = replace_once(
            src,
            '        "source_focus": source_focus_diag,\n',
            '        "source_focus": source_focus_diag,\n        "source_jurisdiction": source_jurisdiction_diag,\n',
            "framing jurisdiction report",
        )
    if "County source-authority recovery" not in src:
        anchor = "        # Save source-extraction hits/misses before any Claude work."
        src = replace_once(src, anchor, MAIN_BRANCH + "        # Save source-extraction hits/misses before any Claude work.", "county fast recovery branch")
    return src, src != original

def main() -> int:
    src = PATH.read_text(encoding="utf-8")
    patched, changed = patch(src)
    required = (
        MARKER,
        "def _county_zero_candidate_fast_recovery",
        "generated_jurisdiction_not_supported_by_source",
        "source_jurisdiction_conflicts_with_generated_county",
        "County source-authority recovery",
        'item["category_key"] = category_key',
    )
    for token in required:
        if token not in patched:
            raise SystemExit(f"False-jurisdiction hotfix verification failed: {token}")
    if changed:
        fd, name = tempfile.mkstemp(prefix="generate.", suffix=".tmp", dir=PATH.parent)
        os.close(fd)
        tmp = Path(name)
        try:
            tmp.write_text(patched, encoding="utf-8")
            py_compile.compile(str(tmp), doraise=True)
            os.replace(tmp, PATH)
        finally:
            tmp.unlink(missing_ok=True)
    py_compile.compile(str(PATH), doraise=True)
    print(f"False-jurisdiction generator hotfix: changed={str(changed).lower()}, verified=true")
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
