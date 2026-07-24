"""Bridge persistent editorial stories into publication-time canonical identity.

The shadow registry reasons about raw source articles.  The production generator may
rewrite those headlines before creating TCT permalinks, so headline-only archive
matching can lose the registry decision and publish several URLs for one story.
This module builds a conservative source/title index from the persistent registry so
publication can retain that identity without enabling broad semantic enforcement.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping, Iterable

from .registry_repair import normalize_identity_title
from .source_identity import normalize_source_identity_url

PUBLICATION_IDENTITY_VERSION = "1.0"


@dataclass(frozen=True)
class PublicationIdentityIndex:
    url_to_story: Mapping[str, str]
    title_to_story: Mapping[str, str]
    safe_story_ids: frozenset[str]
    canonical_titles: Mapping[str, str]

    def resolve(self, item: Mapping[str, Any] | None) -> str:
        if not isinstance(item, Mapping):
            return ""
        for key in ("source_url", "link", "url"):
            normalized = normalize_source_identity_url(item.get(key))
            story_id = self.url_to_story.get(normalized, "") if normalized else ""
            if story_id and story_id in self.safe_story_ids:
                return story_id

        identity_title = normalize_identity_title(
            item.get("source_headline") or item.get("headline") or item.get("title")
        )
        story_id = self.title_to_story.get(identity_title, "") if identity_title else ""
        return story_id if story_id in self.safe_story_ids else ""


def _story_items(payload: Mapping[str, Any] | None) -> Iterable[tuple[str, Mapping[str, Any]]]:
    if not isinstance(payload, Mapping):
        return ()
    stories = payload.get("stories", {})
    if isinstance(stories, Mapping):
        return (
            (str(story_id), story)
            for story_id, story in stories.items()
            if isinstance(story, Mapping)
        )
    if isinstance(stories, list):
        return (
            (str(story.get("story_id") or ""), story)
            for story in stories
            if isinstance(story, Mapping) and story.get("story_id")
        )
    return ()


def _is_safe_duplicate_story(story: Mapping[str, Any]) -> bool:
    """Keep this bridge narrower than general story identity.

    Follow-ups and related-event relationships remain outside publication enforcement.
    Duplicate/source consolidation stories are safe because they represent parallel
    coverage of the same stage, not a new editorial milestone.
    """
    relationships = {
        str(row.get("relationship") or "").strip().lower()
        for row in (story.get("relationship_history") or [])
        if isinstance(row, Mapping)
    }
    if relationships & {"follow_up", "follow-up", "related"}:
        return False
    return True


def build_publication_identity_index(
    payload: Mapping[str, Any] | None,
) -> PublicationIdentityIndex:
    url_candidates: dict[str, set[str]] = {}
    title_candidates: dict[str, set[str]] = {}
    safe_story_ids: set[str] = set()
    canonical_titles: dict[str, str] = {}

    for story_id, story in _story_items(payload):
        if not story_id:
            continue
        canonical_titles[story_id] = str(story.get("canonical_title") or "")
        if _is_safe_duplicate_story(story):
            safe_story_ids.add(story_id)

        titles: list[Any] = list(story.get("titles") or [])
        for candidate in story.get("title_candidates") or []:
            if isinstance(candidate, Mapping):
                titles.append(candidate.get("title"))
        for title in titles:
            normalized = normalize_identity_title(title)
            if normalized:
                title_candidates.setdefault(normalized, set()).add(story_id)

        urls: list[Any] = []
        urls.extend(story.get("sources") or [])
        for row in story.get("timeline") or []:
            if isinstance(row, Mapping):
                urls.extend((row.get("url"), row.get("source")))
        for candidate in story.get("title_candidates") or []:
            if isinstance(candidate, Mapping):
                urls.append(candidate.get("source"))
        for value in urls:
            normalized = normalize_source_identity_url(value)
            if normalized:
                url_candidates.setdefault(normalized, set()).add(story_id)

    url_to_story = {
        value: next(iter(story_ids))
        for value, story_ids in url_candidates.items()
        if len(story_ids) == 1
    }
    title_to_story = {
        value: next(iter(story_ids))
        for value, story_ids in title_candidates.items()
        if len(story_ids) == 1
    }
    return PublicationIdentityIndex(
        url_to_story=url_to_story,
        title_to_story=title_to_story,
        safe_story_ids=frozenset(safe_story_ids),
        canonical_titles=canonical_titles,
    )
