"""Conservative, cross-headline custom authority for named breaking incidents.

Custom headlines often identify a person while later publisher headlines describe
a role (e.g., "detective arrested") instead.  The identity proof requires the
actual full name in the reporting, a short publication window, shared locality,
and multiple concrete incident facts.  It does not merge by surname, subject,
occupation, broad topic, or editorial/registry story ID alone.
"""
from __future__ import annotations

from datetime import date
from email.utils import parsedate_to_datetime
import re

_NAME = re.compile(
    r"(?=\b([A-Z][a-zA-Z'’-]{2,})(?:\s+[A-Z]\.?)?\s+([A-Z][a-zA-Z'’-]{2,})\b)"
)
_BAD_FIRST = {
    "st", "saint", "lucie", "county", "city", "police", "sheriff",
    "detective", "deputy", "officer", "firefighter", "paramedic",
    "judge", "doctor", "dr", "the", "florida", "indian", "river",
    "vero", "port", "fort", "new", "state", "federal", "agency",
}
_BAD_LAST = {
    "county", "city", "river", "beach", "sound", "police",
    "sheriff", "arrested", "arrest", "charged", "charge", "felony",
    "dui", "dies", "died", "crash", "court", "office", "department",
    "vehicle", "report", "says", "said", "monday", "tuesday",
}
_LOCALITIES = {
    "st-lucie": r"\bst[.]?\s*lucie\b|\bfort pierce\b|\bport st[.]?\s*lucie\b",
    "indian-river": r"\bindian river\b|\bvero beach\b|\bsebastian\b",
    "martin": r"\bmartin county\b|\bstuart\b|\bhobe sound\b|\bpalm city\b",
    "palm-beach": r"\bpalm beach\b|\bjupiter\b",
}
_FACTS = {
    "dui": r"\bdui\b|\bdriving under the influence\b|\bdrunk driving\b",
    "crash": r"\bcrash(?:ed)?\b|\bcollision\b|\bwreck\b",
    "agency_vehicle": r"\b(?:agency|department|sheriff(?:'s|s)? office|police)\s+(?:owned\s+)?vehicle\b|\bpatrol (?:car|vehicle)\b",
    "injury": r"\bserious (?:bodily|personal) injur(?:y|ies)\b|\bcritical(?:ly)? injur",
    "arrest": r"\barrest(?:ed)?\b|\bcharged\b|\bturn(?:ed)? himself in\b|\bsurrendered\b",
    "warrant": r"\bwarrant\b",
    "shooting": r"\bshooting\b|\bshot\b|\bgunfire\b",
    "homicide": r"\bhomicide\b|\bmurder(?:ed)?\b|\bmanslaughter\b",
    "assault": r"\bassault\b|\bbattery\b",
    "burglary": r"\bburglary\b|\bburglarized\b|\bbreak-in\b",
    "fraud": r"\bfraud\b|\bembezzlement\b",
    "theft": r"\btheft\b|\bstolen\b|\brobbery\b",
    "fire": r"\b(?:structure|house|brush|wild)\s*fire\b|\barson\b",
    "rescue": r"\brescu(?:e|ed)\b",
}
_STRONG = {
    "dui", "crash", "agency_vehicle", "injury", "shooting", "homicide",
    "assault", "burglary", "fraud", "theft", "fire",
}
_MONTHS = (
    "january", "february", "march", "april", "may", "june", "july",
    "august", "september", "october", "november", "december",
)
_MONTH_RX = re.compile(
    r"\b(" + "|".join(_MONTHS) + r")\s+(\d{1,2})\b", re.I
)
_CRASH_RX = re.compile(r"\b(?:crash|collision|wreck)\b", re.I)


def _text(item):
    return " ".join(str(item.get(k) or "")[:5000] for k in (
        "headline", "teaser", "body", "article_text", "source_headline",
    ))


def _publication_date(item):
    # Generated archive entries carry ISO slug dates; incoming feeds often carry
    # RFC-2822 source_published/published timestamps and have NO slug yet. The
    # pre-publication guard must work for both representations.
    for key in ("slug", "date", "source_published", "published_raw",
                "published", "first_published"):
        raw = str(item.get(key) or "").strip()
        if not raw:
            continue
        iso = re.search(r"\b20\d{2}-\d{2}-\d{2}\b", raw)
        if iso:
            try:
                return date.fromisoformat(iso.group(0))
            except ValueError:
                continue
        try:
            return parsedate_to_datetime(raw).date()
        except (TypeError, ValueError, IndexError):
            continue
    return None


def _subject(authority):
    headline = str(authority.get("headline") or "")
    teaser = str(authority.get("teaser") or "")
    for match in _NAME.finditer(headline):
        first, last = match.group(1), match.group(2)
        if first.casefold() in _BAD_FIRST or last.casefold() in _BAD_LAST:
            continue
        pattern = _person_pattern(first, last)
        # Repeated in the custom reporting: not incidental headline/title words.
        if pattern.search(teaser or headline):
            return first.casefold(), last.casefold()
    return None


def _person_pattern(first, last):
    # A publisher may insert a middle initial: Tyler Horstman / Tyler A. Horstman.
    return re.compile(
        r"(?<![a-z])" + re.escape(first) +
        r"\s+(?:[A-Z]\.?\s+)?"+re.escape(last)+r"(?![a-z])",
        re.I,
    )


def _facts(text):
    return {key for key, pat in _FACTS.items() if re.search(pat, text, re.I)}


def _localities(text):
    return {key for key, pat in _LOCALITIES.items() if re.search(pat, text, re.I)}


def _dated_crashes(text):
    # Compare explicitly attributed CRASH dates only; publication dates are not
    # incident dates. A new crash by the same person must remain separate.
    result = set()
    for m in _CRASH_RX.finditer(text):
        for date_match in _MONTH_RX.finditer(text[max(0, m.start()-35):m.end()+35]):
            month = _MONTHS.index(date_match.group(1).lower()) + 1
            day = int(date_match.group(2))
            if 1 <= day <= 31:
                result.add((month, day))
    return result


def same_named_incident_as_custom(candidate, authority):
    """Return (proven, key). No guessed identity or destructive fuzzy redirects."""
    if not isinstance(candidate, dict) or not isinstance(authority, dict):
        return False, ""
    if not (authority.get("is_custom") or authority.get("authoritative_custom")):
        return False, ""
    if candidate.get("is_custom") or candidate.get("authoritative_custom"):
        return False, ""
    left_date = _publication_date(candidate)
    right_date = _publication_date(authority)
    if not left_date or not right_date or abs((left_date-right_date).days) > 3:
        return False, ""
    name = _subject(authority)
    if not name:
        return False, ""
    first, last = name
    candidate_headline = str(candidate.get("headline") or "")
    candidate_lead = " ".join((
        candidate_headline, str(candidate.get("teaser") or "")[:350],
        str(candidate.get("body") or candidate.get("article_text") or "")[:350],
    ))
    # The person must be the subject of the incoming lead, not a passing
    # mention deep in a different report or a mere URL keyword.
    subject_pattern = _person_pattern(first, last)
    if not subject_pattern.search(candidate_lead):
        return False, ""

    # A different full name prominently in the publisher's headline is an
    # explicit competing primary subject, even when the custom subject is quoted.
    for m in _NAME.finditer(candidate_headline):
        other_first, other_last = m.group(1), m.group(2)
        if other_first.casefold() in _BAD_FIRST or other_last.casefold() in _BAD_LAST:
            continue
        if (other_first.casefold(), other_last.casefold()) != name:
            return False, ""

    candidate_text, authority_text = _text(candidate), _text(authority)
    if not (_localities(candidate_text) & _localities(authority_text)):
        return False, ""
    shared_facts = _facts(candidate_text) & _facts(authority_text)
    # Name + county + generic arrest is not enough: require three independently
    # shared incident facts, including a specific kind of event.
    if len(shared_facts) < 3 or not (shared_facts & _STRONG):
        return False, ""
    candidate_crashes = _dated_crashes(candidate_text)
    authority_crashes = _dated_crashes(authority_text)
    if candidate_crashes and authority_crashes and not (candidate_crashes & authority_crashes):
        return False, ""

    key = (
        "named-custom-incident|" + first + "-" + last + "|" +
        right_date.isoformat() + "|" + ",".join(sorted(shared_facts))
    )
    return True, key


def potential_named_custom_collision(candidate, authority):
    """A deliberately broader *hold* predicate, never redirect authority.

    This runs independently at the final publication boundary.  A probable
    duplicate with only two independently matching facts must not be allowed
    to publish simply because the higher-confidence automatic merger required
    three. A false positive halts publishing for human review; it NEVER
    redirects, erases, or alters an existing article.
    """
    if not isinstance(candidate, dict) or not isinstance(authority, dict):
        return False
    if not (authority.get("is_custom") or authority.get("authoritative_custom")):
        return False
    if candidate.get("is_custom") or candidate.get("authoritative_custom"):
        return False
    source_slug = str(candidate.get("slug") or "")
    authority_slug = str(authority.get("slug") or "")
    if not source_slug or not authority_slug or source_slug == authority_slug:
        return False

    candidate_day = _publication_date(candidate)
    authority_day = _publication_date(authority)
    if not candidate_day or not authority_day:
        return False
    if abs((candidate_day - authority_day).days) > 3:
        return False
    subject = _subject(authority)
    if not subject:
        return False
    first, last = subject
    lead = " ".join(str(candidate.get(k) or "")[:350] for k in (
        "headline", "teaser", "body", "article_text"
    ))
    if not _person_pattern(first, last).search(lead):
        return False
    # A differently named headline subject needs independent editorial review,
    # not silent suppression as the custom person's report.
    for match in _NAME.finditer(str(candidate.get("headline") or "")):
        given, family = match.group(1).lower(), match.group(2).lower()
        if given in _BAD_FIRST or family in _BAD_LAST:
            continue
        if (given, family) != subject:
            return False

    left, right = _text(candidate), _text(authority)
    if not (_localities(left) & _localities(right)):
        return False
    shared = _facts(left) & _facts(right)
    if len(shared) < 2 or not (shared & _STRONG):
        return False
    left_crashes, right_crashes = _dated_crashes(left), _dated_crashes(right)
    if left_crashes and right_crashes and not left_crashes.intersection(right_crashes):
        return False
    return True


def assert_no_unresolved_named_custom_collisions(archive):
    """Fail closed before deployment if an active archive escaped custom authority.

    Unlike automatic canonical cleanup, this independent barrier does *not*
    guess a redirect target or change content. It prevents the publication
    transaction from succeeding until a possible same-person incident can be
    resolved safely. Earlier unaffected production output remains on the site.
    """
    rows = [row for row in (archive or []) if isinstance(row, dict) and row.get("slug")]
    authorities = [
        row for row in rows
        if (row.get("is_custom") or row.get("authoritative_custom"))
        and _subject(row)
    ]
    generated = [
        row for row in rows
        if not (row.get("is_custom") or row.get("authoritative_custom"))
    ]
    collisions = []
    for candidate in generated:
        for authority in authorities:
            if potential_named_custom_collision(candidate, authority):
                collisions.append({
                    "generated_slug": candidate["slug"],
                    "custom_slug": authority["slug"],
                })
                # Limit exceptions to a useful bounded diagnostic.
                if len(collisions) >= 10:
                    break
        if len(collisions) >= 10:
            break
    if collisions:
        details = "; ".join(
            f"{item['generated_slug']} -> custom:{item['custom_slug']}"
            for item in collisions
        )
        raise RuntimeError(
            "Custom canonical publication safety gate FAILED: unresolved "
            "possible duplicate(s) of manually published custom articles. "
            "The update must not deploy a second live permalink; investigate "
            f"and resolve these identities first: {details}"
        )
    return True
