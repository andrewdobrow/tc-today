"""Narrow authority rule for editor-selected images in custom TCT articles.

Unlike automated publisher-image mirrors, an image supplied directly in a
custom article may already be hosted on TCT's CDN; no external publisher URL
exists. Treat that as first-party editorial authority only with exact persisted
custom identity and image field agreement. Never infer this for RSS sources.
"""
from typing import Any, Callable


def is_editor_authored_custom_hosted_image(
    archive_row: Any,
    rss_image_url: str,
    *,
    absolute_image_url: Callable[[Any], str],
    is_tct_image: Callable[[str], bool],
) -> bool:
    if not isinstance(archive_row, dict):
        return False
    if not (archive_row.get("is_custom") or archive_row.get("authoritative_custom")):
        return False
    if not str(archive_row.get("custom_id") or "").strip():
        return False
    url = absolute_image_url(rss_image_url)
    if not url or not is_tct_image(url):
        return False
    # A prior mirror-status flag may survive a manual custom-image change.
    # The editor-authored custom identity and exact three-field agreement, not
    # a stale delivery flag, are the authority for this first-party exception.
    return all(
        absolute_image_url(archive_row.get(field)) == url
        for field in ("image_url", "source_image_url", "hosted_image_url")
    )
