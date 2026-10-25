"""Narrow, durable custom-authority match for follow-up coverage of a named death.

Do not merge simply because a surname, profession, county, or family relationship
is shared.  A recent same-event date, the original deceased's full name, death
framing, and the same fire-service agency are all needed for this contract.
"""
from __future__ import annotations

from datetime import datetime, date
import re

# Matches complete adjacent first+last names through overlapping lookahead; the
# generic incident extractor can otherwise swallow 'Austin Hodge Dies' as a
# three-word purported name or consume 'Paramedic Austin Hodge' first.
_NAME = r"([A-Z][a-zA-Z'’-]{1,29}\s+[A-Z][a-zA-Z'’-]{1,29})"
_NAME_BEFORE_DEATH = re.compile(
    rf"(?<![A-Za-z]){_NAME}\s+(?:dies?|died|dead|was killed|passed away|"
    r"has died|is dead)\b", re.I,
)
_DEATH = re.compile(r"\b(?:died|dies|death|dead|mourns?|passed away|line.of.duty|killed)\b", re.I)
_LOCALITIES = {
    "st-lucie": re.compile(r"\bst\.?\s*lucie\b|\bfort pierce\b|\bport st\.?\s*lucie\b", re.I),
    "martin": re.compile(r"\bmartin county\b|\bstuart\b|\bhobe sound\b", re.I),
    "indian-river": re.compile(r"\bindian river county\b|\bvero beach\b|\bsebastian\b", re.I),
    "palm-beach": re.compile(r"\bpalm beach county\b|\bwest palm beach\b", re.I),
}
_AGENCY_FAMILIES = {
    "fire-service": re.compile(r"\b(?:firefighter|fire district|fire rescue|fire department|firefighter.paramedic)\b", re.I),
    "law-enforcement": re.compile(r"\b(?:police department|police officer|sheriff.s office|sheriff.s deputy)\b", re.I),
    "school": re.compile(r"\b(?:school district|teacher|school board)\b", re.I),
}

def _shared_agency_context(left, right):
    locality = next((name for name, regex in _LOCALITIES.items() if regex.search(left) and regex.search(right)), "")
    family = next((name for name, regex in _AGENCY_FAMILIES.items() if regex.search(left) and regex.search(right)), "")
    return locality, family
_BAD_FIRST = {"st", "lucie", "county", "fire", "firefighter", "paramedic", "station", "second", "brother", "district"}
_BAD_LAST = {"county", "district", "firefighter", "paramedic", "hodge's", "brother", "dies", "died"}


def _text(item):
    return " ".join(str(item.get(key) or "")[:5000] for key in (
        "headline", "title", "teaser", "body", "article_text", "source_headline", "source_title"
    )).strip()


def _name(value):
    words = value.split()
    if len(words) != 2:
        return ""
    if words[0].casefold() in _BAD_FIRST or words[-1].casefold() in _BAD_LAST:
        return ""
    return " ".join(words).casefold().replace("’", "'")


def _source_subject(authority):
    text = _text(authority)
    for m in _NAME_BEFORE_DEATH.finditer(text):
        named = _name(m.group(1))
        if named:
            return named
    return ""


def _calendar_date(row):
    # Compare date of the death event, not lastmod (which changes on updates).
    slug = str(row.get("slug") or "")
    if re.match(r"^20\d{2}-\d\d-\d\d-", slug):
        try:
            return date.fromisoformat(slug[:10])
        except ValueError:
            pass
    for key in ("first_published", "date", "source_published", "published_raw"):
        value = str(row.get(key) or "")
        if m := re.search(r"20\d{2}-\d\d-\d\d", value):
            try:
                return date.fromisoformat(m.group())
            except ValueError:
                pass
    return None


def same_named_death_as_custom(candidate, authority):
    """Return (proven, narrow durable identity key), failing closed if uncertain.

    This authority intentionally requires both reports to concern the same
    *current* death announcement. A 2025 story about the deceased's sibling is
    independently publishable, even where it names the 2026 subject as a relative.
    """
    if not isinstance(candidate, dict) or not isinstance(authority, dict):
        return False, ""
    if not (authority.get("is_custom") or authority.get("authoritative_custom")):
        return False, ""
    subject = _source_subject(authority)
    if not subject:
        return False, ""
    incoming = _text(candidate)
    reference = _text(authority)
    if not (_DEATH.search(incoming[:850]) and _DEATH.search(reference[:850])):
        return False, ""
    locality, agency_family = _shared_agency_context(incoming, reference)
    if not locality or not agency_family:
        return False, ""
    # Require explicit complete name, never just a surname or 'his brother'.
    if not re.search(r"(?<![A-Za-z])" + re.escape(subject) + r"(?![A-Za-z])", incoming, re.I):
        return False, ""
    # A different named death explicitly framed in the lead is not this death.
    # For instance, Jarius Hodge died in 2025; his brother Austin was quoted.
    subject_match = re.search(r"(?<![A-Za-z])" + re.escape(subject) + r"(?![A-Za-z])", incoming, re.I)
    for match in _NAME_BEFORE_DEATH.finditer(incoming[:600]):
        lead_name = _name(match.group(1))
        # Secondary background about a relative is not the main death when the
        # subject has already been named earlier in the article.
        if lead_name and lead_name != subject and (not subject_match or match.start() < subject_match.start()):
            return False, ""
        if lead_name == subject:
            break
    left_date = _calendar_date(candidate)
    right_date = _calendar_date(authority)
    if left_date is None or right_date is None or abs((left_date - right_date).days) > 2:
        return False, ""
    # An exact person + same event-date + same named agency + death context is
    # stronger than multiword headline overlap, without broadening fuzzy matching.
    key = f"named-death-custom|{subject.replace(' ', '-')}|{right_date.isoformat()}|{locality}|{agency_family}"
    return True, key
